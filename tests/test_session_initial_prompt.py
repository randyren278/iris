import io

from iris.sessions import SessionController


class Process:
    pid = 42
    stdin = io.StringIO()
    stdout = io.StringIO()

    def poll(self):
        return None


class Launcher:
    def launch(self, *_args, **_kwargs):
        return Process()


class Registry:
    def add(self, **_kwargs):
        return type("Session", (), {"id": 1, "pid": 42})()

    def remove(self, _session_id):
        return None


class Transport:
    def __init__(self):
        self.prompts = []

    def register(self, _session, _process):
        return None

    def send(self, session_id, prompt):
        self.prompts.append((session_id, prompt))
        return True


def test_streaming_claude_receives_its_initial_prompt_after_registration(tmp_path):
    transport = Transport()
    controller = SessionController(Registry(), Launcher(), transport=transport)

    controller.launch("claude", cwd=tmp_path, prompt="inspect tests")

    assert transport.prompts == [(1, "inspect tests")]
