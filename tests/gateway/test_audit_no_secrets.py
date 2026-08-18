from iris.audit import AuditLog


def test_rejected_inbound_audit_uses_digest_not_message_body_or_token(tmp_path):
    body = "xoxb-secret do not persist"
    metadata = AuditLog.rejected_inbound(event_id="Ev-1", user_id="U-stranger", body=body)
    path = tmp_path / "audit.jsonl"
    AuditLog(path).append("rejected", **metadata)

    stored = path.read_text()
    assert body not in stored
    assert "body_sha256" in stored
