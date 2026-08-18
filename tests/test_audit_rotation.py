from iris.audit import AuditLog


def test_audit_rotates_before_exceeding_size_budget(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(path, max_bytes=50)
    audit.append("one", detail="x" * 30)
    audit.append("two", detail="y" * 30)

    assert path.with_suffix(".jsonl.1").exists()
    assert '"two"' in path.read_text()
