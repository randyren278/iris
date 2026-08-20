import pathlib

import pytest

import iris.config as config_module
from iris.config import Config, applescript_sender, load


def test_load_parses_complete_terminal_managed_configuration(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        'chatdb = "/tmp/messages.db"\n'
        'state_path = "/tmp/poller.json"\n'
        'allowlist = ["+15550001", "me@example.com"]\n'
        'self_chat_guid = "iMessage;-;self"\n'
        'self_command_suffix = " :: Iris"\n'
        'slack_allowlist = ["U123", "U456"]\n'
        'projects_root = "/tmp/projects"\n'
    )

    result = load(path)

    assert result.chatdb == pathlib.Path("/tmp/messages.db")
    assert result.state_path == pathlib.Path("/tmp/poller.json")
    assert result.allowlist == ("+15550001", "me@example.com")
    assert result.self_chat_guid == "iMessage;-;self"
    assert result.self_command_suffix == " :: Iris"
    assert result.slack_allowlist == ("U123", "U456")
    assert result.projects_root == pathlib.Path("/tmp/projects")


def test_load_uses_safe_defaults_for_omitted_optional_configuration(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("")
    result = load(path)
    assert result.chatdb == config_module.DEFAULT_CHATDB
    assert result.state_path == config_module.DEFAULT_STATE_PATH
    assert result.allowlist == ()
    assert result.self_chat_guid is None
    assert result.self_command_suffix == " - Iris"
    assert result.slack_allowlist == ()
    assert result.projects_root == config_module.DEFAULT_PROJECTS_ROOT


@pytest.mark.parametrize("value", ["not-an-array", ["ok", 3], {"x": "y"}, 7])
def test_load_rejects_malformed_imessage_allowlist(tmp_path, value):
    path = tmp_path / "config.toml"
    import json
    # TOML scalars/arrays need different rendering; build explicit fixtures.
    if isinstance(value, str):
        encoded = f'"{value}"'
    elif isinstance(value, list):
        encoded = '["ok", 3]'
    elif isinstance(value, dict):
        encoded = '{x = "y"}'
    else:
        encoded = str(value)
    path.write_text(f"allowlist = {encoded}\n")
    with pytest.raises(ValueError, match="allowlist must be an array of strings"):
        load(path)


@pytest.mark.parametrize("source", [
    'slack_allowlist = "U123"\n',
    'slack_allowlist = ["U123", 9]\n',
    'slack_allowlist = {user = "U123"}\n',
])
def test_load_rejects_malformed_slack_allowlist(tmp_path, source):
    path = tmp_path / "config.toml"
    path.write_text(source)
    with pytest.raises(ValueError, match="slack_allowlist must be an array of Slack user IDs"):
        load(path)


def test_missing_config_file_is_not_silently_replaced_with_defaults(tmp_path):
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "missing.toml")


def test_applescript_sender_delegates_lazily(monkeypatch):
    calls = []
    monkeypatch.setattr("iris.sender.send_to_chat", lambda handle, text: calls.append((handle, text)) or True)
    assert applescript_sender("chat-guid", "hello") is True
    assert calls == [("chat-guid", "hello")]


def test_config_can_still_be_constructed_explicitly_for_nonproduction_harnesses(tmp_path):
    sender = lambda _handle, _text: True
    value = Config(chatdb=tmp_path / "db", state_path=tmp_path / "state", sender=sender,
                   allowlist=("a",), slack_allowlist=("U1",), projects_root=tmp_path)
    assert value.sender is sender
    assert value.allowlist == ("a",)
    assert value.slack_allowlist == ("U1",)
