from iris.runtime import RuntimeStatus, StatusStore


def test_status_store_is_atomic_and_only_online_fresh_status_is_healthy(tmp_path):
    now = [100.0]
    store = StatusStore(tmp_path / "runtime.json", clock=lambda: now[0])
    store.write(RuntimeStatus(1, "boot", "online", 100.0))
    assert store.healthy(max_age=10)
    now[0] = 111.0
    assert not store.healthy(max_age=10)
    store.write(RuntimeStatus(1, "boot", "offline", 111.0))
    assert not store.healthy(max_age=10)
    assert (tmp_path / "runtime.json").stat().st_mode & 0o777 == 0o600


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
