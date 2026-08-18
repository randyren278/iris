"""request_approval must deny, not crash, when a socket peer sends non-object JSON."""
import json
import socket
import threading
import uuid
from pathlib import Path

from iris.approvals import request_approval


def _respond_with(path, line):
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen()

    def serve_once():
        connection, _address = server.accept()
        with connection:
            connection.recv(4096)
            connection.sendall(line.encode() + b"\n")
        server.close()

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    return thread


def test_client_denies_when_response_is_not_a_json_object(tmp_path):
    path = Path("/tmp") / f"iris-{uuid.uuid4().hex}.sock"
    thread = _respond_with(path, json.dumps([1, 2, 3]))
    try:
        assert request_approval(path, "Bash") is False
    finally:
        thread.join(2)
        if path.exists():
            path.unlink()
