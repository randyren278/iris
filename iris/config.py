"""Runtime configuration.

The chat.db path and the sender are injectable so the whole gateway can be
exercised against the fake harness with no phone attached (CP-3.1). Production
values are the defaults; tests construct a Config explicitly.
"""
import dataclasses
import pathlib
import tomllib

DEFAULT_CHATDB = pathlib.Path.home() / "Library/Messages/chat.db"
DEFAULT_STATE_PATH = pathlib.Path.home() / ".iris" / "poller-state.json"
DEFAULT_CONFIG_PATH = pathlib.Path.home() / ".iris" / "config.toml"
DEFAULT_PROJECTS_ROOT = pathlib.Path.home() / "Developer"


def applescript_sender(handle, text):
    """Reply to an existing Messages chat; imported lazily for tests."""
    from iris.sender import send_to_chat
    return send_to_chat(handle, text)


@dataclasses.dataclass
class Config:
    chatdb: pathlib.Path = DEFAULT_CHATDB
    state_path: pathlib.Path = DEFAULT_STATE_PATH
    # Called as sender(handle, text). Swapped for a recording stub in tests.
    sender: callable = applescript_sender
    # Handles permitted to drive the gateway. Terminal-only mutation (P3.3):
    # no inbound message path may add to this.
    allowlist: tuple = ()
    # The one self-chat allowed to carry locally-sent commands. This is a
    # chat GUID, not a handle, so an accidental "- Iris" sent to someone else
    # cannot control the gateway.
    self_chat_guid: str | None = None
    self_command_suffix: str = " - Iris"
    # Slack identities are stable user IDs, never display names or emails.
    slack_allowlist: tuple = ()
    projects_root: pathlib.Path = DEFAULT_PROJECTS_ROOT


def load(path=DEFAULT_CONFIG_PATH):
    """Load terminal-managed configuration; inbound messages never write it."""
    with pathlib.Path(path).open("rb") as config_file:
        data = tomllib.load(config_file)
    allowlist = data.get("allowlist", [])
    slack_allowlist = data.get("slack_allowlist", [])
    if not isinstance(allowlist, list) or not all(isinstance(h, str) for h in allowlist):
        raise ValueError("allowlist must be an array of strings")
    if not isinstance(slack_allowlist, list) or not all(isinstance(user_id, str) for user_id in slack_allowlist):
        raise ValueError("slack_allowlist must be an array of Slack user IDs")
    return Config(
        chatdb=pathlib.Path(data.get("chatdb", DEFAULT_CHATDB)),
        state_path=pathlib.Path(data.get("state_path", DEFAULT_STATE_PATH)),
        allowlist=tuple(allowlist),
        self_chat_guid=data.get("self_chat_guid"),
        self_command_suffix=data.get("self_command_suffix", " - Iris"),
        slack_allowlist=tuple(slack_allowlist),
        projects_root=pathlib.Path(data.get("projects_root", DEFAULT_PROJECTS_ROOT)),
    )
