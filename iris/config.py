"""Runtime configuration.

The chat.db path and the sender are injectable so the whole gateway can be
exercised against the fake harness with no phone attached (CP-3.1). Production
values are the defaults; tests construct a Config explicitly.
"""
import dataclasses
import pathlib

DEFAULT_CHATDB = pathlib.Path.home() / "Library/Messages/chat.db"


def applescript_sender(handle, text):
    """Send via Messages. Imported lazily so tests never touch osascript."""
    from iris.sender import send
    return send(handle, text)


@dataclasses.dataclass
class Config:
    chatdb: pathlib.Path = DEFAULT_CHATDB
    # Called as sender(handle, text). Swapped for a recording stub in tests.
    sender: callable = applescript_sender
    # Handles permitted to drive the gateway. Terminal-only mutation (P3.3):
    # no inbound message path may add to this.
    allowlist: tuple = ()
