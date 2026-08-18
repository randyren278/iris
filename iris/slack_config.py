"""Slack credentials loaded exclusively from the macOS Keychain.

The gateway never accepts Slack tokens through configuration files or
environment variables.  Keeping the lookup small and injectable lets the
offline test suite prove that boundary without a Slack workspace.
"""
from __future__ import annotations

import dataclasses
import subprocess
from collections.abc import Callable


KEYCHAIN_SERVICE = "com.iris.slack"
APP_TOKEN_ACCOUNT = "iris-app-token"
BOT_TOKEN_ACCOUNT = "iris-bot-token"


class CredentialError(RuntimeError):
    """A required Keychain item is unavailable, without exposing its value."""


@dataclasses.dataclass(frozen=True)
class SlackCredentials:
    app_token: str
    bot_token: str


Runner = Callable[..., subprocess.CompletedProcess[str]]


def keychain_token(account: str, *, runner: Runner = subprocess.run) -> str:
    """Return one token from the login Keychain without leaking command output."""
    result = runner(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE,
         "-a", account, "-w"],
        check=False,
        capture_output=True,
        text=True,
    )
    token = (result.stdout or "").strip()
    # Keychain Access on current macOS may store the entered Name as the
    # item's label even when its visible "Where" value is the service.  Try
    # that equivalent lookup only after the canonical service lookup fails.
    if result.returncode != 0 or not token:
        result = runner(
            ["security", "find-generic-password", "-l", KEYCHAIN_SERVICE,
             "-a", account, "-w"],
            check=False,
            capture_output=True,
            text=True,
        )
        token = (result.stdout or "").strip()
    if result.returncode != 0 or not token:
        raise CredentialError(f"Slack credential unavailable for account {account!r}")
    return token


def load_credentials(*, runner: Runner = subprocess.run) -> SlackCredentials:
    """Load both Socket Mode credentials from the macOS login Keychain."""
    return SlackCredentials(
        app_token=keychain_token(APP_TOKEN_ACCOUNT, runner=runner),
        bot_token=keychain_token(BOT_TOKEN_ACCOUNT, runner=runner),
    )
