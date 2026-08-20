"""Runtime configuration.

Terminal-managed only: the daemon reads this file, and no inbound message
path may write it.
"""
import dataclasses
import pathlib
import tomllib

DEFAULT_CONFIG_PATH = pathlib.Path.home() / ".iris" / "config.toml"
DEFAULT_PROJECTS_ROOT = pathlib.Path.home() / "Developer"


@dataclasses.dataclass
class Config:
    # Slack identities are stable user IDs, never display names or emails.
    slack_allowlist: tuple = ()
    projects_root: pathlib.Path = DEFAULT_PROJECTS_ROOT


def load(path=DEFAULT_CONFIG_PATH):
    """Load terminal-managed configuration; inbound messages never write it."""
    with pathlib.Path(path).open("rb") as config_file:
        data = tomllib.load(config_file)
    slack_allowlist = data.get("slack_allowlist", [])
    if not isinstance(slack_allowlist, list) or not all(isinstance(user_id, str) for user_id in slack_allowlist):
        raise ValueError("slack_allowlist must be an array of Slack user IDs")
    return Config(
        slack_allowlist=tuple(slack_allowlist),
        projects_root=pathlib.Path(data.get("projects_root", DEFAULT_PROJECTS_ROOT)),
    )
