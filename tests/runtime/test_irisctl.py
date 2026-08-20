import os
from types import SimpleNamespace

import iris.irisctl as irisctl
from iris.runtime import RuntimeStatus, StatusStore


def test_status_reports_missing_and_existing_runtime(tmp_path, capsys):
    assert irisctl.main(["status", "--state-dir", str(tmp_path)]) == 1
    assert "Iris is not running" in capsys.readouterr().out

    store = StatusStore(tmp_path / "runtime.json")
    store.write(RuntimeStatus(os.getpid(), "boot", "starting", store._clock()))
    assert irisctl.main(["status", "--state-dir", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "RuntimeStatus" in output
    assert "starting" in output


def test_verify_online_uses_fresh_live_online_runtime_status(tmp_path, capsys):
    store = StatusStore(tmp_path / "runtime.json")
    store.write(RuntimeStatus(os.getpid(), "boot", "online", store._clock()))
    assert irisctl.main(["verify-online", "--state-dir", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "Iris is online"

    store.write(RuntimeStatus(os.getpid(), "boot", "offline", store._clock()))
    assert irisctl.main(["verify-online", "--state-dir", str(tmp_path)]) == 1
    assert capsys.readouterr().out.strip() == "Iris is not online"


def test_verify_online_samples_health_once(monkeypatch, tmp_path, capsys):
    calls = []

    class Store:
        def __init__(self, path):
            assert path == tmp_path / "runtime.json"

        def healthy(self):
            calls.append("healthy")
            return True

    monkeypatch.setattr(irisctl, "StatusStore", Store)
    assert irisctl.main(["verify-online", "--state-dir", str(tmp_path)]) == 0
    assert calls == ["healthy"]
    assert capsys.readouterr().out.strip() == "Iris is online"


def test_terminal_rearm_removes_persistent_disarm_and_restarts(tmp_path, monkeypatch, capsys):
    disarm = tmp_path / "disarmed"
    disarm.write_text("disarmed\n")
    calls = []
    monkeypatch.setattr(irisctl, "_kickstart", lambda: calls.append("restart"))

    assert irisctl.main(["rearm", "--state-dir", str(tmp_path)]) == 0

    assert not disarm.exists()
    assert calls == ["restart"]
    assert capsys.readouterr().out.strip() == "Iris re-armed and restarted."


def test_terminal_rearm_is_idempotent_when_marker_is_already_absent(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(irisctl, "_kickstart", lambda: calls.append("restart"))
    assert irisctl.main(["rearm", "--state-dir", str(tmp_path)]) == 0
    assert calls == ["restart"]


def test_restart_delegates_to_launchctl_wrapper(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(irisctl, "_kickstart", lambda: calls.append("restart"))
    assert irisctl.main(["restart", "--state-dir", str(tmp_path)]) == 0
    assert calls == ["restart"]


def test_kickstart_targets_current_gui_launchd_domain(monkeypatch):
    calls = []
    monkeypatch.setattr(irisctl.subprocess, "run", lambda command, check: calls.append((command, check)) or SimpleNamespace())
    monkeypatch.setattr(irisctl.os, "getuid", lambda: 501)
    irisctl._kickstart()
    assert calls == [([
        "launchctl", "kickstart", "-k", "gui/501/com.iris.gateway"
    ], True)]
