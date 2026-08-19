from iris.approvals import ApprovalQueue, request_approval


def test_approval_client_stays_denied_without_a_running_local_server(tmp_path):
    assert not request_approval(tmp_path / "missing.sock", "Bash")


def test_approval_queue_denies_and_cleans_up_when_notification_fails():
    def fail(_text):
        raise OSError("Slack unavailable")
    queue = ApprovalQueue(notifier=fail)
    assert queue.request("write file", timeout=1) is False
    assert queue.pending() == ()
