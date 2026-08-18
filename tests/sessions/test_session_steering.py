import io
import json

from iris.session_transport import SessionTransport


class Input:
    def __init__(self):
        self.value = ""
        self.flushed = False

    def write(self, value):
        self.value += value

    def flush(self):
        self.flushed = True


class Process:
    def __init__(self):
        self.stdin = Input()
        self.stdout = io.StringIO()

    def poll(self):
        return None


class Thread:
    def __init__(self, *, target, args, daemon):
        self.target, self.args = target, args

    def start(self):
        pass


def test_follow_up_is_written_to_the_live_session_stream():
    transport = SessionTransport(lambda *_args: None, thread_factory=Thread)
    transport.register(type("Session", (), {"id": 3})(), Process())
    process = transport._processes[3]

    assert transport.send(3, "continue with tests")
    assert json.loads(process.stdin.value)["message"]["content"] == "continue with tests"
    assert process.stdin.flushed
