import io

from iris.session_transport import SessionTransport


class Process:
    def __init__(self, output):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(output)

    def poll(self):
        return None


class ImmediateThread:
    def __init__(self, *, target, args, daemon):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


def test_agent_result_waits_for_and_returns_to_its_origin_thread():
    notices = []
    transport = SessionTransport(lambda *value: notices.append(value), thread_factory=ImmediateThread)
    transport.register(type("Session", (), {"id": 7})(), Process('{"type":"result","result":"Tests passed"}\n'))
    transport.bind_thread(7, "D-1", "1.1")

    assert notices == [("D-1", "1.1", "Tests passed"), ("D-1", "1.1", "Session finished.")]


def test_terminal_result_repeated_after_assistant_message_is_posted_once():
    notices = []
    output = ('{"type":"assistant","message":{"content":[{"text":"Tests passed"}]}}\n'
              '{"type":"result","result":"Tests passed"}\n')
    transport = SessionTransport(lambda *value: notices.append(value), thread_factory=ImmediateThread)
    transport.register(type("Session", (), {"id": 8})(), Process(output))
    transport.bind_thread(8, "D-1", "1.1")

    assert notices == [("D-1", "1.1", "Tests passed"), ("D-1", "1.1", "Session finished.")]
