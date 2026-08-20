"""Ownership-lock edge paths: a lost race must never look like ownership."""
import os
import pathlib

import pytest

from iris.runtime import SingleInstanceLock


def test_release_without_acquire_leaves_another_owners_lock_intact(tmp_path):
    path = tmp_path / "runtime.lock"
    path.mkdir()
    (path / "pid").write_text("4242")

    SingleInstanceLock(path).release()

    # A daemon that never won the lock must not delete the winner's state.
    assert (path / "pid").read_text() == "4242"


def test_losing_the_recreate_race_reports_failure_rather_than_ownership(tmp_path, monkeypatch):
    path = tmp_path / "runtime.lock"
    path.mkdir()
    (path / "pid").write_text("999999999")
    os.utime(path, (1.0, 1.0))  # ancient -> stale, so the reclaim path is taken

    original = pathlib.Path.mkdir

    def mkdir(self, *args, **kwargs):
        if self == path:
            raise FileExistsError(str(self))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "mkdir", mkdir)
    lock = SingleInstanceLock(path)

    assert lock.acquire() is False
    assert lock.acquired is False


def test_vanished_lock_directory_counts_as_stale(tmp_path):
    lock = SingleInstanceLock(tmp_path / "absent.lock")
    assert lock._stale(max_age=300) is True


@pytest.mark.parametrize("pid_text", ["", "not-a-pid", "999999999"])
def test_missing_unreadable_or_dead_owner_pid_counts_as_stale(tmp_path, pid_text):
    path = tmp_path / "runtime.lock"
    path.mkdir()
    if pid_text:
        (path / "pid").write_text(pid_text)

    lock = SingleInstanceLock(path, clock=lambda: os.stat(path).st_mtime)
    assert lock._stale(max_age=300) is True


def test_owner_pid_belonging_to_another_user_is_not_stale(tmp_path, monkeypatch):
    path = tmp_path / "runtime.lock"
    path.mkdir()
    (path / "pid").write_text("1")

    def denied(_pid, _signal):
        raise PermissionError()

    monkeypatch.setattr(os, "kill", denied)
    lock = SingleInstanceLock(path, clock=lambda: os.stat(path).st_mtime)

    # A live process owned by someone else is still a live owner: reclaiming it
    # would put two daemons on Socket Mode at once.
    assert lock._stale(max_age=300) is False
