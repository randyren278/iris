import stat
import threading
import time
import uuid
from pathlib import Path

from iris.approval_hook import MAX_SUMMARY_CHARS, summarize_tool_call
from iris.approvals import ApprovalQueue, ApprovalServer, request_approval


def test_approval_socket_is_owner_only():
    queue = ApprovalQueue(notifier=lambda _message: None)
    server = ApprovalServer(Path("/tmp") / f"iris-{uuid.uuid4().hex}.sock", queue)
    server.start()
    try:
        assert stat.S_IMODE(server.path.stat().st_mode) == 0o600
    finally:
        server.close()


def test_hook_blocks_until_operator_decision(tmp_path):
    queue = ApprovalQueue(notifier=lambda _message: None)
    server = ApprovalServer(Path("/tmp") / f"iris-{uuid.uuid4().hex}.sock", queue, timeout=1)
    server.start()
    result = []
    thread = threading.Thread(target=lambda: result.append(request_approval(server.path, "run tool")))
    thread.start()
    while not queue.pending():
        time.sleep(0.005)
    assert thread.is_alive()
    queue.resolve(True)
    thread.join(1)
    server.close()
    assert result == [True]


def test_hook_summary_includes_exact_tool_arguments_and_is_bounded():
    summary = summarize_tool_call({
        "tool_name": "Bash",
        "tool_input": {"command": "pytest -q", "description": "run deterministic suite"},
    })
    assert summary.startswith("Bash ")
    assert '"command":"pytest -q"' in summary
    assert '"description":"run deterministic suite"' in summary

    long_summary = summarize_tool_call({"tool_name": "Write", "tool_input": {"content": "x" * 5000}})
    assert len(long_summary) <= MAX_SUMMARY_CHARS + len("Write ")
    assert long_summary.endswith("...")


def test_approval_request_rejects_partial_origin_before_connecting(tmp_path):
    assert not request_approval(tmp_path / "missing.sock", "run tool", channel_id="D-1")
