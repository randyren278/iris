from iris.approvals import ApprovalQueue


def test_timeout_notifies_operator_of_denial():
    notices = []
    assert ApprovalQueue(notifier=notices.append).request("network call", timeout=0.01) is False
    assert notices[-1] == "Approval 1 timed out; denied."
