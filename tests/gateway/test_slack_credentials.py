"""CP-S0: Slack credentials come only from the macOS Keychain."""
from types import SimpleNamespace

import pytest

from iris.slack_config import (
    APP_TOKEN_ACCOUNT,
    BOT_TOKEN_ACCOUNT,
    KEYCHAIN_SERVICE,
    CredentialError,
    keychain_token,
    load_credentials,
)


def test_keychain_lookup_uses_explicit_service_and_account():
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="xapp-test-token\n")

    assert keychain_token(APP_TOKEN_ACCOUNT, runner=runner) == "xapp-test-token"
    assert calls == [(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE,
         "-a", APP_TOKEN_ACCOUNT, "-w"],
        {"check": False, "capture_output": True, "text": True},
    )]


def test_lookup_error_does_not_include_keychain_output():
    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=44, stdout="secret-value", stderr="details")

    with pytest.raises(CredentialError) as error:
        keychain_token(APP_TOKEN_ACCOUNT, runner=runner)
    assert "secret-value" not in str(error.value)
    assert "details" not in str(error.value)


def test_keychain_lookup_falls_back_to_label_created_by_keychain_access():
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        if "-s" in command:
            return SimpleNamespace(returncode=44, stdout="")
        return SimpleNamespace(returncode=0, stdout="xapp-label-token\n")

    assert keychain_token(APP_TOKEN_ACCOUNT, runner=runner) == "xapp-label-token"
    assert [call[0] for call in calls] == [
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE,
         "-a", APP_TOKEN_ACCOUNT, "-w"],
        ["security", "find-generic-password", "-l", KEYCHAIN_SERVICE,
         "-a", APP_TOKEN_ACCOUNT, "-w"],
    ]


def test_loads_both_required_tokens():
    values = iter(["xapp-1\n", "xoxb-2\n"])

    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=next(values))

    credentials = load_credentials(runner=runner)
    assert credentials.app_token == "xapp-1"
    assert credentials.bot_token == "xoxb-2"
    assert (APP_TOKEN_ACCOUNT, BOT_TOKEN_ACCOUNT) == ("iris-app-token", "iris-bot-token")
