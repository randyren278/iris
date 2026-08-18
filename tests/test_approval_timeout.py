from iris.approvals import ApprovalQueue


def test_timeout_denies_when_operator_does_not_reply():
    notices = []
    queue = ApprovalQueue(notifier=notices.append)
    assert queue.request("network call", timeout=0.01) is False
    assert queue.pending() == ()
