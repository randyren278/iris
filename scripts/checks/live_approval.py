#!/usr/bin/env python3
"""Crown-jewel live check: a real `claude` subprocess against a real ApprovalServer.

Proves CLAUDE.md's approval invariant end-to-end, not against
tests/slack_fakes.py or any other test double: with nobody answering the
approval prompt, a real Claude tool call is denied and the file is not
created; with an operator "y", it is allowed and the file is created. Both
runs assert the ApprovalQueue actually received a request -- the notifier
only fires when Iris's real PreToolUse hook (iris.approval_hook, wired the
same way iris/launcher.py wires it for a live session) connects to the
socket and sends a summary -- so a pass here means the hook fired, not just
that the file did or didn't appear.

Run via scripts/checks/live_approval.sh, never in the deterministic suite:

    .venv/bin/python scripts/checks/live_approval.py
"""
from __future__ import annotations

import json
import os
import pathlib
import signal
import sys
import tempfile
import threading
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from iris.approvals import ApprovalQueue, ApprovalServer  # noqa: E402
from iris.launcher import Launcher  # noqa: E402

PROMPT = "Write the text OK to a file named probe.txt in the current directory using your Write tool."
QUEUE_TIMEOUT = 20.0
SUBPROCESS_DEADLINE = 90.0


def _drain(process, sink: list[str]) -> None:
    try:
        for line in process.stdout:
            sink.append(line.rstrip("\n"))
    except (OSError, ValueError):
        pass


def _kill(process) -> None:
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.kill()
        except ProcessLookupError:
            pass


def _run(*, responder: bool, label: str) -> dict:
    notified: list[str] = []
    queue = ApprovalQueue(notifier=notified.append)

    with tempfile.TemporaryDirectory(prefix=f"iris-live-approval-{label}-cwd-") as workspace_str, \
         tempfile.TemporaryDirectory(prefix=f"iris-live-approval-{label}-sock-") as sock_dir_str:
        workspace = pathlib.Path(workspace_str)
        socket_path = pathlib.Path(sock_dir_str) / "approval.sock"

        server = ApprovalServer(socket_path, queue, timeout=QUEUE_TIMEOUT)
        server.start()

        responder_thread = None
        process = None
        lines: list[str] = []
        try:
            launcher = Launcher(approval_socket=socket_path, streaming=True)
            process = launcher.launch("claude", cwd=workspace, prompt=PROMPT)

            reader = threading.Thread(target=_drain, args=(process, lines), daemon=True)
            reader.start()

            process.stdin.write(json.dumps({
                "type": "user", "message": {"role": "user", "content": PROMPT},
            }) + "\n")
            process.stdin.flush()

            if responder:
                def respond():
                    deadline = time.monotonic() + QUEUE_TIMEOUT
                    while time.monotonic() < deadline:
                        if queue.pending():
                            queue.resolve(True)
                            return
                        time.sleep(0.05)
                responder_thread = threading.Thread(target=respond, daemon=True)
                responder_thread.start()

            deadline = time.monotonic() + SUBPROCESS_DEADLINE
            while process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.2)
            timed_out = process.poll() is None
            if timed_out:
                _kill(process)
            try:
                process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
            reader.join(timeout=5)
        finally:
            if process is not None and process.poll() is None:
                _kill(process)
            server.close()
            if responder_thread is not None:
                responder_thread.join(timeout=1)

        probe_created = (workspace / "probe.txt").exists()
        probe_content = (workspace / "probe.txt").read_text() if probe_created else None

    return {
        "label": label,
        "hook_fired": bool(notified),
        "notified": notified,
        "returncode": None if process is None else process.returncode,
        "timed_out": timed_out,
        "probe_created": probe_created,
        "probe_content": probe_content,
        "stdout_tail": lines[-15:],
    }


def _report(result: dict) -> None:
    print(f"--- {result['label']} ---")
    print(f"hook_fired={result['hook_fired']} notified={result['notified']}")
    print(f"returncode={result['returncode']} timed_out={result['timed_out']}")
    print(f"probe_created={result['probe_created']} probe_content={result['probe_content']!r}")
    print("stdout tail:")
    for line in result["stdout_tail"]:
        print(f"  {line}")


def main() -> int:
    ok = True

    print("=== Run 1: no responder -> tool call must be DENIED ===")
    deny = _run(responder=False, label="deny")
    _report(deny)
    if not deny["hook_fired"]:
        print("FAIL: PreToolUse hook never connected to the approval socket; "
              "this run did not exercise a real tool call and proves nothing.",
              file=sys.stderr)
        ok = False
    if deny["probe_created"]:
        print("FAIL: probe.txt was created with no approval responder; deny-by-default failed.",
              file=sys.stderr)
        ok = False

    print()
    print("=== Run 2: responder answers 'y' -> tool call must be ALLOWED ===")
    allow = _run(responder=True, label="allow")
    _report(allow)
    if not allow["hook_fired"]:
        print("FAIL: PreToolUse hook never connected to the approval socket on the allow run.",
              file=sys.stderr)
        ok = False
    if not allow["probe_created"]:
        print("FAIL: probe.txt was not created after the responder approved the tool call.",
              file=sys.stderr)
        ok = False
    elif allow["probe_content"] is None or "OK" not in allow["probe_content"]:
        print(f"FAIL: probe.txt content did not contain the expected text: {allow['probe_content']!r}",
              file=sys.stderr)
        ok = False

    print()
    if ok:
        print("PASS: deny-by-default and approve-after-y both proven against a real claude subprocess "
              "and a real ApprovalServer.")
        return 0
    print("FAIL: see above.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
