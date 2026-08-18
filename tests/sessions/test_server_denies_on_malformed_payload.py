"""ApprovalServer._handle must deny, not allow, when a payload cannot be read."""
import json
import socket
import uuid
from pathlib import Path

from iris.approvals import ApprovalQueue, ApprovalServer


def _send(path, line):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        client.connect(str(path))
        client.sendall(line.encode() + b"\n")
        return json.loads(client.makefile("r", encoding="utf-8").readline())


def _server(queue):
    return ApprovalServer(Path("/tmp") / f"iris-{uuid.uuid4().hex}.sock", queue, timeout=1)


def test_server_denies_on_malformed_json():
    queue = ApprovalQueue(notifier=lambda _message: None)
    server = _server(queue)
    server.start()
    try:
        assert _send(server.path, "not json") == {"approved": False}
    finally:
        server.close()


def test_server_denies_when_summary_key_is_missing():
    queue = ApprovalQueue(notifier=lambda _message: None)
    server = _server(queue)
    server.start()
    try:
        assert _send(server.path, json.dumps({"not_summary": "x"})) == {"approved": False}
    finally:
        server.close()
