"""Operator-run Slack Socket Mode reachability probe for CP-S0.

This module is deliberately not imported by the daemon.  It is a narrow live
acceptance check whose tokens are loaded from the Keychain at execution time.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from iris.slack_config import CredentialError, load_credentials
from iris.runtime import StatusStore


def _sdk():
    try:
        from slack_sdk.errors import SlackApiError
        from slack_sdk.socket_mode import SocketModeClient
        from slack_sdk.web import WebClient
    except ImportError as error:  # pragma: no cover - exercised at live gate
        raise RuntimeError("slack-sdk is required; install Iris dependencies") from error
    return SocketModeClient, WebClient, SlackApiError


def authenticate(credentials):
    """Open a Socket Mode connection and verify the bot token with Slack."""
    SocketModeClient, WebClient, SlackApiError = _sdk()
    # auth.test validates the bot token; connect() validates the app token and
    # establishes the outbound-only Socket Mode WebSocket.
    WebClient(token=credentials.bot_token).auth_test()
    client = SocketModeClient(app_token=credentials.app_token,
                              web_client=WebClient(token=credentials.bot_token))
    try:
        try:
            client.connect()
        except SlackApiError as error:
            code = error.response.get("error", "unknown_error")
            raise RuntimeError(f"Slack authentication failed: {code}") from error
    finally:
        client.close()


def send_to_only_dm(credentials, text):
    """Post a manually requested probe only when there is one active Iris DM.

    Slack can retain an empty IM record after a reinstall.  A current direct
    conversation has at least one message, so selecting exactly one active DM
    avoids guessing an operator identity during initial provisioning.
    S1 replaces this one-off helper with routing from the inbound event's
    channel and thread identifiers.
    """
    _SocketModeClient, WebClient, _SlackApiError = _sdk()
    client = WebClient(token=credentials.bot_token)
    conversations = client.conversations_list(types="im", limit=200)["channels"]
    active_conversations = [
        conversation
        for conversation in conversations
        if client.conversations_history(channel=conversation["id"], limit=1)["messages"]
    ]
    if len(active_conversations) != 1:
        raise RuntimeError("expected exactly one active Iris DM before sending a probe")
    client.chat_postMessage(channel=active_conversations[0]["id"], text=text)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify Iris Slack Socket Mode credentials")
    parser.add_argument("--send", help="reserved for the CP-S0 DM round-trip")
    parser.add_argument("--acceptance", action="store_true",
                        help="reserved for CP-FINAL live acceptance")
    parser.add_argument("--jarvis-acceptance", action="store_true",
                        help="verify the local daemon is online, then post the S7 live-test marker")
    args = parser.parse_args(argv)
    try:
        credentials = load_credentials()
        authenticate(credentials)
        if args.jarvis_acceptance:
            store = StatusStore(pathlib.Path.home() / ".iris" / "runtime.json")
            if not store.healthy():
                raise RuntimeError("Iris daemon is not online; run irisctl status before live acceptance")
            send_to_only_dm(credentials, "Iris is online for S7 Jarvis acceptance. Send a normal question, then a coding task and follow-up.")
        if args.acceptance:
            send_to_only_dm(credentials, "iris CP-FINAL acceptance")
        if args.send:
            send_to_only_dm(credentials, args.send)
    except (CredentialError, RuntimeError) as error:
        print(f"Slack probe failed: {error}", file=sys.stderr)
        return 1
    print("Slack Socket Mode authenticated.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    raise SystemExit(main())
