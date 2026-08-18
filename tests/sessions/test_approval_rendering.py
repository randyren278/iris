from iris.approvals import ApprovalQueue, PendingApproval


def test_approval_prompt_is_readable_and_actionable():
    rendered = ApprovalQueue.render(PendingApproval(3, "run git push"))
    assert "Approval 3" in rendered
    assert "run git push" in rendered
    assert "y or n" in rendered
