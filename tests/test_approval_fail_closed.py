from iris.approvals import request_approval


def test_approval_client_stays_denied_without_a_running_local_server(tmp_path):
    assert not request_approval(tmp_path / "missing.sock", "Bash")
