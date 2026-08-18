"""Slack Socket Mode transport for the Iris gateway.

This module owns only transport concerns.  It deliberately echoes accepted
DMs in S1; command parsing and agent work are added in later slices.
"""
from __future__ import annotations

import dataclasses
import logging
import threading
import time
from collections.abc import Callable, Iterable

from iris.slack_config import SlackCredentials


LOG = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class SlackMessage:
    """The minimal, routing-safe shape of an inbound Slack DM."""

    event_id: str
    user_id: str
    channel_id: str
    text: str
    ts: str
    thread_ts: str | None = None
    bot_id: str | None = None
    subtype: str | None = None
    channel_type: str | None = None

    @property
    def reply_thread_ts(self) -> str:
        return self.thread_ts or self.ts

    @classmethod
    def from_envelope(cls, envelope: dict) -> SlackMessage | None:
        """Decode a Slack Events API envelope without accepting other events."""
        if envelope.get("type") != "events_api":
            return None
        event = envelope.get("event")
        if not isinstance(event, dict) or event.get("type") != "message":
            return None
        required = ("user", "channel", "text", "ts")
        if not all(isinstance(event.get(key), str) and event[key] for key in required):
            return None
        event_id = envelope.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            return None
        return cls(
            event_id=event_id,
            user_id=event["user"],
            channel_id=event["channel"],
            text=event["text"],
            ts=event["ts"],
            thread_ts=event.get("thread_ts") if isinstance(event.get("thread_ts"), str) else None,
            bot_id=event.get("bot_id") if isinstance(event.get("bot_id"), str) else None,
            subtype=event.get("subtype") if isinstance(event.get("subtype"), str) else None,
            channel_type=event.get("channel_type") if isinstance(event.get("channel_type"), str) else None,
        )


class SlackGateway:
    """Allowlist and echo inbound Slack DMs with retry de-duplication."""

    def __init__(self, allowed_user_ids: Iterable[str], client, *, handler=None, audit=None,
                 on_inbound=None, on_outbound=None):
        self.allowed_user_ids = frozenset(allowed_user_ids)
        self.client = client
        self.handler = handler
        self.audit = audit
        self.on_inbound = on_inbound
        self.on_outbound = on_outbound
        self._seen_event_ids: set[str] = set()
        self._dedupe_lock = threading.Lock()

    def handle_envelope(self, envelope: dict) -> bool:
        message = SlackMessage.from_envelope(envelope)
        if message is None:
            return False
        # Socket Mode dispatches listeners from a thread pool, so retries of
        # the same event can arrive on different threads concurrently; the
        # check-then-add below must be atomic or both can pass.
        with self._dedupe_lock:
            if message.event_id in self._seen_event_ids:
                return False
            self._seen_event_ids.add(message.event_id)
        if message.channel_type != "im" or message.bot_id or message.subtype:
            return False
        if message.user_id not in self.allowed_user_ids:
            # Never log an unallowlisted message body.
            LOG.warning("ignored Slack event from non-allowlisted user", extra={"event_id": message.event_id})
            if self.audit:
                from iris.audit import AuditLog
                self.audit.append("rejected_inbound", **AuditLog.rejected_inbound(
                    event_id=message.event_id, user_id=message.user_id, body=message.text
                ))
            return False
        if self.audit:
            self.audit.append("inbound", event_id=message.event_id, user_id=message.user_id,
                              channel_id=message.channel_id, thread_ts=message.reply_thread_ts)
        if self.on_inbound:
            self.on_inbound()
        response = self.handler(message) if self.handler else message.text
        self.client.post_message(
            channel_id=message.channel_id,
            text=response,
            thread_ts=message.reply_thread_ts,
        )
        if self.on_outbound:
            self.on_outbound()
        return True

    def run_forever(self, source, *, stop: Callable[[], bool] | None = None) -> None:
        source.run(self.handle_envelope, stop=stop)


class SlackWebClient:
    """Small production wrapper whose interface is easy to record in tests."""

    def __init__(self, bot_token: str):
        try:
            from slack_sdk import WebClient
        except ImportError as error:  # pragma: no cover - live dependency
            raise RuntimeError("slack-sdk is required; install Iris dependencies") from error
        self._client = WebClient(token=bot_token)

    def post_message(self, *, channel_id: str, text: str, thread_ts: str) -> None:
        self._client.chat_postMessage(channel=channel_id, text=text, thread_ts=thread_ts)


class SocketModeEventSource:
    """Outbound-only Socket Mode source; it starts no network listener."""

    def __init__(self, credentials: SlackCredentials):
        self.credentials = credentials

    def run(self, handler: Callable[[dict], bool], *, stop: Callable[[], bool] | None = None,
            on_connected=None, on_disconnected=None) -> None:
        try:
            from slack_sdk.socket_mode import SocketModeClient
            from slack_sdk.socket_mode.response import SocketModeResponse
        except ImportError as error:  # pragma: no cover - live dependency
            raise RuntimeError("slack-sdk is required; install Iris dependencies") from error

        client = SocketModeClient(app_token=self.credentials.app_token)

        def observe(_socket_client, raw_message, _raw_text):
            if isinstance(raw_message, dict):
                LOG.info("received Socket Mode envelope", extra={"type": raw_message.get("type")})

        def receive(socket_client, request):
            socket_client.send_socket_mode_response(
                SocketModeResponse(envelope_id=request.envelope_id)
            )
            # Socket Mode carries ``events_api`` on the outer envelope; the
            # inner Events API payload has its own ``event_callback`` type.
            # Preserve the transport type for our narrow decoder.
            handler({**request.payload, "type": request.type})

        client.message_listeners.append(observe)
        client.socket_mode_request_listeners.append(receive)
        try:
            client.connect()
            if on_connected:
                on_connected()
        except Exception as error:
            if on_disconnected:
                on_disconnected(error)
            raise
        try:
            while not stop or not stop():
                time.sleep(0.1)
        finally:
            client.close()
            if on_disconnected:
                on_disconnected()
