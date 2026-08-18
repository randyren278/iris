import json

from iris.audit import AuditLog


def test_audit_records_operational_event_metadata(tmp_path):
    path = tmp_path / "audit.jsonl"
    AuditLog(path).append("launch", session_id=3, tool="claude")

    record = json.loads(path.read_text())
    assert record["event"] == "launch"
    assert record["session_id"] == 3
