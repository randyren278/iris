from types import SimpleNamespace

from iris.conversation import ClaudeTextBackend, ConversationMessage


def test_claude_conversation_backend_has_no_tools_and_scrubs_nested_agent_environment():
    calls = []
    backend = ClaudeTextBackend(
        run=lambda *args, **kwargs: calls.append((args, kwargs)) or SimpleNamespace(
            returncode=0, stdout='{"result":"Hello from Iris"}'
        ),
        environ={"PATH": "x", "CLAUDECODE": "nested"},
    )

    assert backend.reply((ConversationMessage("user", "hello"),), ()) == "Hello from Iris"
    command, options = calls[0]
    assert "--tools" in command[0] and command[0][command[0].index("--tools") + 1] == ""
    assert options["env"] == {"PATH": "x"}


def test_missing_claude_binary_returns_a_user_facing_reply():
    backend = ClaudeTextBackend(run=lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    assert "temporarily unavailable" in backend.reply((ConversationMessage("user", "hello"),), ())
