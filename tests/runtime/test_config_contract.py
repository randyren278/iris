import pathlib

import pytest

import iris.config as config_module
from iris.config import Config, load


def test_load_parses_complete_terminal_managed_configuration(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        'slack_allowlist = ["U123", "U456"]\n'
        'projects_root = "/tmp/projects"\n'
    )

    result = load(path)

    assert result.slack_allowlist == ("U123", "U456")
    assert result.projects_root == pathlib.Path("/tmp/projects")


def test_load_uses_safe_defaults_for_omitted_optional_configuration(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("")
    result = load(path)
    assert result.slack_allowlist == ()
    assert result.projects_root == config_module.DEFAULT_PROJECTS_ROOT


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


def test_unknown_configuration_keys_are_ignored_rather_than_trusted(tmp_path):
    """A stale iMessage-era config on disk must not break the Slack daemon."""
    path = tmp_path / "config.toml"
    path.write_text(
        'chatdb = "/tmp/messages.db"\n'
        'allowlist = ["+15550001"]\n'
        'slack_allowlist = ["U123"]\n'
    )

    result = load(path)

    assert result.slack_allowlist == ("U123",)
    assert not hasattr(result, "chatdb")
    assert not hasattr(result, "allowlist")


def test_missing_config_file_is_not_silently_replaced_with_defaults(tmp_path):
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "missing.toml")


def test_config_can_still_be_constructed_explicitly_for_nonproduction_harnesses(tmp_path):
    value = Config(slack_allowlist=("U1",), projects_root=tmp_path)
    assert value.slack_allowlist == ("U1",)
    assert value.projects_root == tmp_path


def test_load_defaults_coding_autonomy_on_and_parses_an_explicit_override(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("")
    assert load(path).coding_autonomy is True

    path.write_text("coding_autonomy = false\n")
    assert load(path).coding_autonomy is False


@pytest.mark.parametrize("source", [
    'coding_autonomy = "true"\n',
    'coding_autonomy = 1\n',
    'coding_autonomy = ["true"]\n',
])
def test_load_rejects_non_boolean_coding_autonomy(tmp_path, source):
    path = tmp_path / "config.toml"
    path.write_text(source)
    with pytest.raises(ValueError, match="coding_autonomy must be a boolean"):
        load(path)
