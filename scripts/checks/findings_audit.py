#!/usr/bin/env python3
"""Assert .review/findings.md is well-formed.

Every finding must have: id (## F-<NNN>: title heading), severity, file,
status (fixed|deferred|test-gap-closed), summary, evidence. Every finding
whose status resolves an action (fixed / test-gap-closed) must name a pytest
node id in its evidence that `pytest --collect-only` can actually resolve --
so a "fixed" claim can't be taken on faith.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FINDINGS = Path(".review/findings.md")
HEADING = re.compile(r"^## (F-\d+): (.+)$")
FIELD = re.compile(r"^-?\s*(severity|file|status|summary|evidence):\s*(.*)$")
NODE_ID = re.compile(r"tests/[\w/]+\.py::[\w:\[\]./-]+")
ACTIONED_STATUSES = {"fixed", "test-gap-closed"}
VALID_STATUSES = ACTIONED_STATUSES | {"deferred"}


def parse_findings(text: str) -> list[dict]:
    findings = []
    current = None
    field = None
    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            if current is not None:
                findings.append(current)
            current = {"id": heading.group(1), "title": heading.group(2), "raw": []}
            field = None
            continue
        if current is None:
            continue
        current["raw"].append(line)
        match = FIELD.match(line)
        if match:
            field = match.group(1)
            current[field] = match.group(2).strip()
        elif field == "evidence" and line.strip():
            current["evidence"] = current.get("evidence", "") + " " + line.strip()
    if current is not None:
        findings.append(current)
    return findings


def collected_node_ids() -> set[str]:
    result = subprocess.run(
        [".venv/bin/python", "-m", "pytest", "-q", "--collect-only"],
        capture_output=True, text=True, check=False,
    )
    ids = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if "::" in line and line.startswith("tests/"):
            ids.add(line)
    return ids


def main() -> int:
    if not FINDINGS.exists():
        sys.stderr.write(f"missing {FINDINGS}\n")
        return 1

    findings = parse_findings(FINDINGS.read_text(encoding="utf-8"))
    if not findings:
        sys.stderr.write("no findings parsed from .review/findings.md\n")
        return 1

    ok = True
    seen_ids = set()
    malformed = []
    bad_status = []
    unresolved_evidence = []

    for finding in findings:
        fid = finding["id"]
        if fid in seen_ids:
            malformed.append(f"{fid}: duplicate finding id")
        seen_ids.add(fid)
        for required in ("severity", "file", "status", "summary", "evidence"):
            if required not in finding or not finding[required]:
                malformed.append(f"{fid}: missing or empty '{required}' field")
        status = finding.get("status", "")
        if status not in VALID_STATUSES:
            bad_status.append(f"{fid}: status {status!r} not in {sorted(VALID_STATUSES)}")

    if malformed or bad_status:
        ok = False
        for msg in malformed + bad_status:
            sys.stderr.write(f"  {msg}\n")

    actioned = [f for f in findings if f.get("status") in ACTIONED_STATUSES]
    if actioned:
        node_ids = collected_node_ids()
        for finding in actioned:
            evidence = " ".join(finding.get("raw", []))
            candidates = NODE_ID.findall(evidence)
            if not candidates:
                unresolved_evidence.append(f"{finding['id']}: status={finding['status']!r} but no "
                                            f"pytest node id found in evidence")
                continue
            if not any(c in node_ids for c in candidates):
                unresolved_evidence.append(f"{finding['id']}: evidence cites {candidates!r}, "
                                            f"none resolve via pytest --collect-only")
        if unresolved_evidence:
            ok = False
            sys.stderr.write("findings claiming fixed/test-gap-closed with unresolved evidence:\n")
            for msg in unresolved_evidence:
                sys.stderr.write(f"  {msg}\n")

    if not ok:
        return 1

    fixed_count = sum(1 for f in findings if f.get("status") in ACTIONED_STATUSES)
    deferred_count = sum(1 for f in findings if f.get("status") == "deferred")
    print(f"{len(findings)} findings well-formed: {fixed_count} fixed/test-gap-closed "
          f"(all with resolvable regression tests), {deferred_count} deferred")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
