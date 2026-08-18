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
