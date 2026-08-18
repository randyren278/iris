"""Self-chat is an owner channel, with Iris's own echoed sends suppressed."""
from iris.config import Config
from iris.main import Gateway
from iris.poller import Poller

SELF = "operator@icloud.com"
SELF_CHAT = f"iMessage;-;{SELF}"


def test_self_chat_is_delivered_without_external_allowlist(fakedb, sender, tmp_path):
    gateway = Gateway(Config(chatdb=fakedb.path, state_path=tmp_path / "state.json",
                             sender=sender, allowlist=(), self_chat_guid=SELF_CHAT))
    gateway.run_once()
    fakedb.inject(SELF, "start a session - Iris", is_from_me=1,
                  chat_guid=SELF_CHAT)

    assert gateway.run_once() == [True]
    assert sender.last() == (SELF_CHAT, "start a session")


def test_untagged_self_message_is_not_a_command(fakedb, sender, tmp_path):
    gateway = Gateway(Config(chatdb=fakedb.path, state_path=tmp_path / "state.json",
                             sender=sender, allowlist=(), self_chat_guid=SELF_CHAT))
    gateway.run_once()
    fakedb.inject(SELF, "ordinary self-chat message", is_from_me=1,
                  chat_guid=SELF_CHAT)

    assert gateway.run_once() == []
    assert sender.sent == []


def test_self_chat_echo_of_iris_reply_is_not_delivered(fakedb, tmp_path):
    poller = Poller(fakedb.path, tmp_path / "state.json", self_chat_guid=SELF_CHAT)
    poller.poll_once()
    poller.track_echo(SELF_CHAT, "Iris: all tests pass")
    fakedb.inject(SELF, "Iris: all tests pass", chat_guid=SELF_CHAT)

    assert poller.poll_once() == []


def test_non_self_inbound_copy_is_not_granted_self_chat_access(fakedb, tmp_path):
    poller = Poller(fakedb.path, tmp_path / "state.json")
    poller.poll_once()
    fakedb.inject("attacker@example.com", "grant access")

    (message,) = poller.poll_once()
    assert not message.is_self_chat
