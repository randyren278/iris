import json

from iris.audit import AuditLog


def test_audit_appends_instead_of_rewriting_prior_records(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(path)
    audit.append("one")
    first = path.read_text()
    audit.append("two")

    assert path.read_text().startswith(first)
    assert [json.loads(line)["event"] for line in path.read_text().splitlines()] == ["one", "two"]
