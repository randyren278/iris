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


def test_concurrent_stale_reclaim_cannot_double_acquire(tmp_path):
    """Two racing reclaimers of the same stale lock must not both win, and
    neither may crash: rmtree()-then-mkdir() is not atomic across processes,
    so an unsynchronized reclaim can let two daemons believe they own
    Socket Mode simultaneously."""
    import threading

    path = tmp_path / "runtime.lock"
    path.mkdir()
    (path / "pid").write_text("999999999")  # a pid very unlikely to exist
    os.utime(path, (1.0, 1.0))  # ancient mtime -> stale by age too

    results = {}
    errors = []

    def run(name):
        try:
            # Every racer reports the current, live test process as its
            # owner, so a winner's claim looks alive to everyone else's
            # staleness check -- isolating the assertion to exclusivity
            # rather than an artifact of a fake PID looking dead too.
            lock = SingleInstanceLock(path, pid=os.getpid)
            results[name] = lock.acquire()
        except Exception as exc:  # noqa: BLE001 - proving no crash of any kind
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(f"t{i}",)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    winners = [name for name, won in results.items() if won]
    assert len(winners) == 1, f"expected exactly one winner, got {winners}"
