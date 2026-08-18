import json
import threading

from iris.audit import AuditLog


def test_concurrent_appends_do_not_raise_or_corrupt_records(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(path, max_bytes=2000)
    errors = []

    def worker(i):
        try:
            for j in range(50):
                audit.append("evt", i=i, j=j, pad="x" * 20)
        except Exception as exc:  # noqa: BLE001 - capturing for the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, errors

    for candidate in (path, path.with_suffix(path.suffix + ".1")):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                json.loads(line)  # every persisted line must be intact JSON
