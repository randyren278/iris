from iris.irisctl import main
from iris.runtime import RuntimeStatus, StatusStore


def test_verify_online_uses_fresh_online_runtime_status(tmp_path):
    store = StatusStore(tmp_path / "runtime.json")
    store.write(RuntimeStatus(1, "boot", "online", store._clock()))
    assert main(["verify-online", "--state-dir", str(tmp_path)]) == 0
    store.write(RuntimeStatus(1, "boot", "offline", store._clock()))
    assert main(["verify-online", "--state-dir", str(tmp_path)]) == 1
