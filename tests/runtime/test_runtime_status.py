import os

from iris.runtime import RuntimeStatus, StatusStore, _pid_is_alive


def test_status_store_is_atomic_and_only_live_online_fresh_status_is_healthy(tmp_path):
    now = [100.0]
    store = StatusStore(tmp_path / "runtime.json", clock=lambda: now[0], pid_alive=lambda pid: pid == 1)
    store.write(RuntimeStatus(1, "boot", "online", 100.0))
    assert store.healthy(max_age=10)
    now[0] = 111.0
    assert not store.healthy(max_age=10)
    store.write(RuntimeStatus(1, "boot", "offline", 111.0))
    assert not store.healthy(max_age=10)
    store.write(RuntimeStatus(2, "boot", "online", 111.0))
    assert not store.healthy(max_age=10)
    assert (tmp_path / "runtime.json").stat().st_mode & 0o777 == 0o600


def test_pid_health_rejects_invalid_and_missing_processes(monkeypatch):
    for pid in (0, -1, True, "12"):
        assert _pid_is_alive(pid) is False

    monkeypatch.setattr(os, "kill", lambda _pid, _signal: (_ for _ in ()).throw(ProcessLookupError()))
    assert _pid_is_alive(123) is False


def test_pid_health_treats_permission_denied_as_existing(monkeypatch):
    monkeypatch.setattr(os, "kill", lambda _pid, _signal: (_ for _ in ()).throw(PermissionError()))
    assert _pid_is_alive(123) is True


def test_pid_health_rejects_other_os_errors(monkeypatch):
    monkeypatch.setattr(os, "kill", lambda _pid, _signal: (_ for _ in ()).throw(OSError()))
    assert _pid_is_alive(123) is False


def test_pid_health_accepts_live_process(monkeypatch):
    calls = []
    monkeypatch.setattr(os, "kill", lambda pid, signal: calls.append((pid, signal)))
    assert _pid_is_alive(123) is True
    assert calls == [(123, 0)]


def test_concurrent_writes_do_not_race_on_the_shared_tmp_file(tmp_path):
    """The heartbeat thread and the main thread both call write() on the same
    StatusStore. Unsynchronized, two threads racing write_text()+replace() on
    the same tmp path can crash with FileNotFoundError when one thread's
    replace() steals the tmp file out from under another's."""
    import threading

    store = StatusStore(tmp_path / "runtime.json")
    errors = []

    def hammer(n):
        for i in range(n):
            try:
                store.write(RuntimeStatus(1, "boot", "online", float(i)))
            except Exception as exc:  # noqa: BLE001 - proving no exception of any kind
                errors.append(exc)

    threads = [threading.Thread(target=hammer, args=(200,)) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
