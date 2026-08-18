import os

from iris.runtime import SingleInstanceLock


def test_old_lock_is_reclaimed_even_when_its_pid_is_reused(tmp_path):
    now = [1000.0]
    path = tmp_path / "runtime.lock"
    path.mkdir()
    (path / "pid").write_text(str(os.getpid()))
    os.utime(path, (100.0, 100.0))
    lock = SingleInstanceLock(path, clock=lambda: now[0], pid=lambda: 99)
    assert lock.acquire(max_age=60)
    assert (path / "pid").read_text() == "99"
