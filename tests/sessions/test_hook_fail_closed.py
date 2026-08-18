from iris.approvals import request_approval


def test_unreachable_approval_daemon_denies(tmp_path):
    assert request_approval(tmp_path / "missing.sock", "run command") is False
