import io
import json
from types import SimpleNamespace

from iris.session_transport import SessionTransport, _event_text


class ImmediateThread:
    def __init__(self, *, target, args, daemon):
        assert daemon is True
        self.target = target
        self.args = args
        self.started = False

    def start(self):
        self.started = True
        self.target(*self.args)


class Input:
    def __init__(self, *, write_error=None, flush_error=None):
        self.writes = []
        self.flushes = 0
        self.write_error = write_error
        self.flush_error = flush_error

    def write(self, text):
        if self.write_error:
            raise self.write_error
        self.writes.append(text)

    def flush(self):
        self.flushes += 1
        if self.flush_error:
            raise self.flush_error


class Process:
    def __init__(self, lines=(), *, returncode=None, stdin=None, stdout=True):
        self.stdin = stdin if stdin is not None else Input()
        self.stdout = io.StringIO("".join(lines)) if stdout else None
        self.returncode = returncode

    def poll(self):
        return self.returncode


def test_register_requires_both_pipes_and_starts_reader_worker():
    notifications = []
    transport = SessionTransport(lambda *args: notifications.append(args), thread_factory=ImmediateThread)
    session = SimpleNamespace(id=1)

    transport.register(session, Process(stdout=False))
    assert transport.send(1, "x") is False

    process = Process((json.dumps({"type": "result", "result": "done"}) + "\n",))
    transport.register(session, process)
    # Reader runs before a target is bound, so output and completion are queued.
    assert notifications == []
    transport.bind_thread(1, "D1", "1.0")
    assert notifications == [("D1", "1.0", "done"), ("D1", "1.0", "Session finished.")]


def test_bind_thread_flushes_pending_in_order_and_future_output_is_direct():
    notifications = []
    transport = SessionTransport(lambda *args: notifications.append(args), thread_factory=lambda **_kwargs: None)
    transport._emit(7, "first")
    transport._emit(7, "second")
    assert notifications == []

    transport.bind_thread(7, "D7", "7.0")
    transport._emit(7, "third")
    assert notifications == [
        ("D7", "7.0", "first"),
        ("D7", "7.0", "second"),
        ("D7", "7.0", "third"),
    ]


def test_emit_deduplicates_identical_consecutive_messages_per_session():
    notifications = []
    transport = SessionTransport(lambda *args: notifications.append(args))
    transport.bind_thread(1, "D1", "1.0")
    transport.bind_thread(2, "D2", "2.0")

    transport._emit(1, "same")
    transport._emit(1, "same")
    transport._emit(2, "same")
    transport._emit(1, "different")
    transport._emit(1, "same")
    assert notifications == [
        ("D1", "1.0", "same"),
        ("D2", "2.0", "same"),
        ("D1", "1.0", "different"),
        ("D1", "1.0", "same"),
    ]


def test_send_encodes_stream_json_and_rejects_missing_dead_or_broken_process():
    transport = SessionTransport(lambda *_args: None)
    assert transport.send(1, "hello") is False

    live = Process()
    transport._processes[1] = live
    assert transport.send(1, "hello") is True
    assert live.stdin.flushes == 1
    assert json.loads(live.stdin.writes[0]) == {
        "type": "user",
        "message": {"role": "user", "content": "hello"},
    }

    transport._processes[2] = Process(returncode=0)
    assert transport.send(2, "late") is False

    transport._processes[3] = Process(stdin=Input(write_error=BrokenPipeError()))
    assert transport.send(3, "broken") is False

    transport._processes[4] = Process(stdin=Input(flush_error=OSError("closed")))
    assert transport.send(4, "broken") is False


def test_remove_erases_process_target_pending_and_dedup_state():
    transport = SessionTransport(lambda *_args: None)
    transport._processes[3] = Process()
    transport._targets[3] = ("D3", "3.0")
    transport._pending[3] = ["queued"]
    transport._last_emitted[3] = "last"

    transport.remove(3)
    assert 3 not in transport._processes
    assert 3 not in transport._targets
    assert 3 not in transport._pending
    assert 3 not in transport._last_emitted
    transport.remove(3)  # idempotent


def test_event_text_handles_plain_result_message_and_malformed_shapes():
    assert _event_text("plain line\n") == "plain line"
    assert _event_text("   \n") is None
    assert _event_text(json.dumps({"type": "result", "result": " done "})) == "done"
    assert _event_text(json.dumps({"type": "result", "result": "   "})) is None
    assert _event_text(json.dumps({"message": {"content": " hello "}})) == "hello"
    assert _event_text(json.dumps({"message": {"content": [
        {"type": "text", "text": "first"},
        {"type": "tool_use", "name": "x"},
        {"text": "second"},
        "ignored",
    ]}})) == "first\nsecond"
    assert _event_text(json.dumps({"message": {"content": []}})) is None
    assert _event_text(json.dumps({"message": []})) is None
    assert _event_text(json.dumps({"unexpected": True})) is None


def test_reader_skips_empty_events_and_always_emits_completion():
    notifications = []
    transport = SessionTransport(lambda *args: notifications.append(args))
    transport.bind_thread(9, "D9", "9.0")
    process = Process((
        json.dumps({"message": {"content": []}}) + "\n",
        "plain\n",
        json.dumps({"type": "result", "result": "answer"}) + "\n",
    ))
    transport._read(9, process)
    assert notifications == [
        ("D9", "9.0", "plain"),
        ("D9", "9.0", "answer"),
        ("D9", "9.0", "Session finished."),
    ]
