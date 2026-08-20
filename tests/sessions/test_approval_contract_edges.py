import io
import json
import threading

from iris.approvals import ApprovalQueue, ApprovalServer, request_approval
from tests.waiting import wait_until


class Connection:
    def __init__(self, payload, *, broken_send=False):
        self.payload = payload
        self.sent = []
        self.broken_send = broken_send

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def makefile(self, *_args, **_kwargs):
        return io.StringIO(self.payload)

    def sendall(self, data):
        if self.broken_send:
            raise BrokenPipeError()
        self.sent.append(json.loads(data.decode()))


class Queue:
    def __init__(self, result=True):
        self.result = result
        self.calls = []

    def request(self, summary, *, timeout, notifier=None, origin=None):
        self.calls.append((summary, timeout, notifier, origin))
        return self.result


def test_queue_rejects_malformed_origin_without_notifying():
    notices = []
    queue = ApprovalQueue(notifier=notices.append)
    invalid = (
        "D1",
        ("D1",),
        ("D1", ""),
        ("D1", 3),
        ["D1", "1.0"],
    )
    for origin in invalid:
        assert queue.request("x", timeout=0, origin=origin) is False
    assert notices == []
    assert queue.pending() == ()


def test_notifier_failure_removes_pending_request_and_denies():
    queue = ApprovalQueue(notifier=lambda _text: (_ for _ in ()).throw(RuntimeError("slack down")))
    assert queue.request("danger", timeout=1) is False
    assert queue.pending() == ()


def test_timeout_notification_failure_cannot_turn_denial_into_exception():
    calls = []

    def notifier(text):
        calls.append(text)
        if "timed out" in text:
            raise RuntimeError("notification path failed")

    queue = ApprovalQueue(notifier=notifier)
    assert queue.request("danger", timeout=0) is False
    assert any("timed out" in item for item in calls)
    assert queue.pending() == ()


def test_resolve_rejects_empty_queue_unknown_id_and_wrong_origin():
    queue = ApprovalQueue(notifier=lambda _text: None)
    assert queue.resolve(True) is False

    result = []
    thread = threading.Thread(target=lambda: result.append(queue.request(
        "danger", timeout=1, origin=("D1", "1.0")
    )))
    thread.start()
    wait_until(queue.pending, message="queue never received a pending approval")

    assert queue.resolve(True, index=999, origin=("D1", "1.0")) is False
    assert queue.resolve(True, index=1, origin=("D2", "2.0")) is False
    assert queue.resolve(True, index=1, origin=None) is False
    assert queue.resolve(False, index=1, origin=("D1", "1.0")) is True
    thread.join(1)
    assert result == [False]


def test_server_handle_accepts_unbound_test_request_and_bound_production_request(tmp_path):
    unbound_queue = Queue(result=True)
    server = ApprovalServer(tmp_path / "unused.sock", unbound_queue, timeout=7)
    connection = Connection('{"summary":"test only"}\n')
    server._handle(connection)
    assert connection.sent == [{"approved": True}]
    assert unbound_queue.calls[0][0:2] == ("test only", 7)
    assert unbound_queue.calls[0][2:] == (None, None)

    notices = []
    bound_queue = Queue(result=False)
    server = ApprovalServer(
        tmp_path / "unused2.sock", bound_queue, timeout=9,
        notifier_for_context=lambda channel, thread: lambda text: notices.append((channel, thread, text)),
    )
    connection = Connection('{"summary":"run pytest","channel_id":"D1","thread_ts":"1.0"}\n')
    server._handle(connection)
    assert connection.sent == [{"approved": False}]
    summary, timeout, notifier, origin = bound_queue.calls[0]
    assert (summary, timeout, origin) == ("run pytest", 9, ("D1", "1.0"))
    notifier("notice")
    assert notices == [("D1", "1.0", "notice")]


def test_server_handle_denies_malformed_payload_classes_without_calling_queue(tmp_path):
    malformed = (
        "not json\n",
        "[]\n",
        "{}\n",
        '{"summary":""}\n',
        '{"summary":3}\n',
        '{"summary":"x","channel_id":"D1"}\n',
        '{"summary":"x","thread_ts":"1.0"}\n',
        '{"summary":"x","channel_id":3,"thread_ts":"1.0"}\n',
    )
    for index, raw in enumerate(malformed):
        queue = Queue()
        server = ApprovalServer(tmp_path / f"unused-{index}.sock", queue)
        connection = Connection(raw)
        server._handle(connection)
        assert connection.sent == [{"approved": False}]
        assert queue.calls == []


def test_server_denies_bound_origin_when_no_origin_notifier_is_configured(tmp_path):
    queue = Queue()
    server = ApprovalServer(tmp_path / "unused.sock", queue)
    connection = Connection('{"summary":"x","channel_id":"D1","thread_ts":"1.0"}\n')
    server._handle(connection)
    assert connection.sent == [{"approved": False}]
    assert queue.calls == []


def test_server_ignores_broken_pipe_while_returning_decision(tmp_path):
    queue = Queue(result=True)
    server = ApprovalServer(tmp_path / "unused.sock", queue)
    server._handle(Connection('{"summary":"x"}\n', broken_send=True))
    assert len(queue.calls) == 1


def test_server_start_replaces_stale_socket_path_and_close_is_idempotent(socket_dir):
    path = socket_dir / "approval.sock"
    path.write_text("stale")
    server = ApprovalServer(path, ApprovalQueue(notifier=lambda _text: None), timeout=0.01)
    server.start()
    try:
        assert path.is_socket()
        assert path.stat().st_mode & 0o777 == 0o600
    finally:
        server.close()
    assert not path.exists()
    server.close()


def test_request_approval_rejects_partial_origin_before_socket_io(tmp_path):
    assert request_approval(tmp_path / "missing.sock", "x", channel_id="D1") is False
    assert request_approval(tmp_path / "missing.sock", "x", thread_ts="1.0") is False


def test_request_approval_denies_nonobject_server_response(socket_dir):
    import socket

    path = socket_dir / "response.sock"
    ready = threading.Event()

    def serve():
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(path))
            listener.listen(1)
            ready.set()
            connection, _ = listener.accept()
            with connection:
                connection.makefile("r", encoding="utf-8").readline()
                connection.sendall(b"[]\n")

    worker = threading.Thread(target=serve)
    worker.start()
    # Without this the listener could die before binding and the assertion
    # below would pass against a missing socket instead of the "[]" reply.
    assert ready.wait(1), "listener thread never bound the socket"
    assert request_approval(path, "x") is False
    worker.join(1)
