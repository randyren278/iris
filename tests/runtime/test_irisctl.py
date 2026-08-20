import iris.irisctl as irisctl
from iris.runtime import RuntimeStatus, StatusStore


def test_verify_online_uses_fresh_online_runtime_status(tmp_path):
    store = StatusStore(tmp_path / "runtime.json")
    store.write(RuntimeStatus(1, "boot", "online", store._clock()))
    assert irisctl.main(["verify-online", "--state-dir", str(tmp_path)]) == 0
    store.write(RuntimeStatus(1, "boot", "offline", store._clock()))
    assert irisctl.main(["verify-online", "--state-dir", str(tmp_path)]) == 1


def test_terminal_rearm_removes_persistent_disarm_and_restarts(tmp_path, monkeypatch):
    disarm = tmp_path / "disarmed"
    disarm.write_text("disarmed\n")
    calls = []
    monkeypatch.setattr(irisctl, "_kickstart", lambda: calls.append("restart"))

    assert irisctl.main(["rearm", "--state-dir", str(tmp_path)]) == 0

    assert not disarm.exists()
    assert calls == ["restart"]
