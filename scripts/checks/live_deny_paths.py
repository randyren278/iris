#!/usr/bin/env python3
"""Live check: every approval failure path CLAUDE.md requires to fail closed.

Exercises `iris.approvals.request_approval` (the hook-facing client) and, for
the two scenarios that require sending something the client helper cannot
construct, a raw socket against a REAL `iris.approvals.ApprovalServer` --
never a fake. All five scenarios must deny and none may raise an uncaught
exception:

  (a) daemon absent           -- nothing listening on the socket path
  (b) socket path unwritable/invalid -- missing parent dir / not a socket
  (c) malformed JSON           -- garbage bytes sent to a live server
  (d) empty/missing summary    -- valid JSON, invalid payload, live server
  (e) timeout                  -- live server, request never resolved

Run via scripts/checks/live_deny_paths.sh, never in the deterministic suite:

    .venv/bin/python scripts/checks/live_deny_paths.py
"""
from __future__ import annotations

import json
import pathlib
import socket
import sys
import tempfile
import time
import traceback

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from iris.approvals import ApprovalQueue, ApprovalServer, request_approval  # noqa: E402


def _raw_send(socket_path: pathlib.Path, payload: bytes, *, connect_timeout: float = 2.0) -> dict:
    """Bypass request_approval to send exact bytes to a live server; used only
    for malformed-input scenarios the client helper cannot express (it always
    emits valid JSON)."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(connect_timeout)
        client.connect(str(socket_path))
        client.settimeout(None)
        client.sendall(payload)
        line = client.makefile("r", encoding="utf-8").readline()
        return json.loads(line)


def scenario_a_daemon_absent() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="iris-deny-a-") as d:
        socket_path = pathlib.Path(d) / "no-listener.sock"
        approved = request_approval(socket_path, "daemon absent")
        return approved is False, f"request_approval returned {approved!r} with nothing listening"


def scenario_b_invalid_paths() -> tuple[bool, str]:
    results = []

    missing_parent = pathlib.Path("/iris-live-deny-nonexistent-parent-dir/socket.sock")
    approved1 = request_approval(missing_parent, "missing parent directory")
    results.append(("missing-parent-dir", approved1))

    with tempfile.TemporaryDirectory(prefix="iris-deny-b-") as d:
        not_a_socket = pathlib.Path(d) / "regular-file"
        not_a_socket.write_text("not a socket")
        approved2 = request_approval(not_a_socket, "path is a regular file, not a socket")
        results.append(("path-is-regular-file", approved2))

    ok = all(approved is False for _label, approved in results)
    return ok, "; ".join(f"{label}={approved!r}" for label, approved in results)


def scenario_c_malformed_json() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="iris-deny-c-") as d:
        socket_path = pathlib.Path(d) / "approval.sock"
        queue = ApprovalQueue(notifier=lambda _msg: None)
        server = ApprovalServer(socket_path, queue, timeout=5.0)
        server.start()
        try:
            response = _raw_send(socket_path, b"this is not json at all\n")
        finally:
            server.close()
        approved = response.get("approved")
        return approved is False, f"live server responded {response!r} to garbage bytes"


def scenario_d_empty_summary() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="iris-deny-d-") as d:
        socket_path = pathlib.Path(d) / "approval.sock"
        queue = ApprovalQueue(notifier=lambda _msg: None)
        server = ApprovalServer(socket_path, queue, timeout=5.0)
        server.start()
        try:
            empty = _raw_send(socket_path, json.dumps({"summary": ""}).encode() + b"\n")
            missing = _raw_send(socket_path, json.dumps({}).encode() + b"\n")
        finally:
            server.close()
        ok = empty.get("approved") is False and missing.get("approved") is False
        return ok, f"empty summary -> {empty!r}; missing summary key -> {missing!r}"


def scenario_e_timeout() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="iris-deny-e-") as d:
        socket_path = pathlib.Path(d) / "approval.sock"
        queue = ApprovalQueue(notifier=lambda _msg: None)
        server = ApprovalServer(socket_path, queue, timeout=1.5)
        server.start()
        try:
            started = time.monotonic()
            approved = request_approval(socket_path, "never resolved, must time out")
            elapsed = time.monotonic() - started
        finally:
            server.close()
        ok = approved is False and elapsed < 30.0
        return ok, f"request_approval returned {approved!r} after {elapsed:.2f}s (server timeout=1.5s)"


SCENARIOS = [
    ("a-daemon-absent", scenario_a_daemon_absent),
    ("b-invalid-socket-path", scenario_b_invalid_paths),
    ("c-malformed-json", scenario_c_malformed_json),
    ("d-empty-or-missing-summary", scenario_d_empty_summary),
    ("e-timeout-never-resolved", scenario_e_timeout),
]


def main() -> int:
    ok = True
    for name, fn in SCENARIOS:
        print(f"--- {name} ---")
        try:
            passed, detail = fn()
        except Exception:  # noqa: BLE001 - a scenario raising is itself the failure
            print(f"FAIL: {name} raised an uncaught exception:", file=sys.stderr)
            traceback.print_exc()
            ok = False
            continue
        print(detail)
        if passed:
            print(f"PASS: {name} denied and did not crash")
        else:
            print(f"FAIL: {name} did not deny as required", file=sys.stderr)
            ok = False
        print()

    if ok:
        print("PASS: all five fail-closed paths denied against a real ApprovalServer.")
        return 0
    print("FAIL: see above.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
