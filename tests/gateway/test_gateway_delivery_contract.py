"""The retained local gateway only records an echo for a send that succeeded."""
from types import SimpleNamespace

from iris.config import Config
from iris.main import Gateway


class RecordingPoller:
    def __init__(self):
        self.echoes = []
        self.runs = []

    def track_echo(self, chat_guid, body):
        self.echoes.append((chat_guid, body))

    def poll_once(self):
        return ()

    def run(self, handler, stop=None):
        self.runs.append((handler, stop))


def _message(handle="+15551234567"):
    return SimpleNamespace(
        handle=handle,
        chat_guid=f"iMessage;-;{handle}",
        body="hello iris",
        is_self_chat=False,
    )


def _gateway(sender, tmp_path, poller):
    config = Config(chatdb=tmp_path / "chat.db", state_path=tmp_path / "state.json",
                    sender=sender, allowlist=("+15551234567",))
    return Gateway(config, poller=poller)


def test_failed_send_is_not_recorded_as_an_echo(tmp_path):
    poller = RecordingPoller()
    gateway = _gateway(lambda _guid, _body: False, tmp_path, poller)

    assert gateway.handle(_message()) is False
    # Tracking an echo that never reached Slack would suppress the operator's
    # next identical message as though Iris had already sent it.
    assert poller.echoes == []


def test_successful_send_is_recorded_as_an_echo(tmp_path):
    poller = RecordingPoller()
    gateway = _gateway(lambda _guid, _body: True, tmp_path, poller)

    assert gateway.handle(_message()) is True
    assert poller.echoes == [("iMessage;-;+15551234567", "hello iris")]


def test_run_forever_delegates_to_the_poller_with_its_stop_signal(tmp_path):
    poller = RecordingPoller()
    gateway = _gateway(lambda _guid, _body: True, tmp_path, poller)
    stop = object()

    gateway.run_forever(stop=stop)

    assert poller.runs == [(gateway.handle, stop)]
