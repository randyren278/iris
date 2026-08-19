from types import SimpleNamespace

import pytest

from iris.main import route_message


class Router:
    def __init__(self): self.messages = []
    def handle(self, message): self.messages.append(message.text); return "command reply"


class Conversation:
    def __init__(self): self.messages = []
    def reply(self, message): self.messages.append(message.text); return "conversation reply"


@pytest.mark.parametrize("text", ["projects", "cd iris", "claude fix it", "codex fix it", "y", "stop"])
def test_explicit_commands_never_enter_conversation_capabilities(text):
    router, conversation = Router(), Conversation()
    assert route_message(SimpleNamespace(text=text), router, conversation) == "command reply"
    assert router.messages == [text]
    assert conversation.messages == []


@pytest.mark.parametrize("text", ["please start codex", "write a file called x", "approve that now", "please stop every session"])
def test_plain_language_actions_remain_conversation_not_control(text):
    router, conversation = Router(), Conversation()
    assert route_message(SimpleNamespace(text=text), router, conversation) == "conversation reply"
    assert router.messages == []
    assert conversation.messages == [text]
