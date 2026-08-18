"""Local safety checks for the Iris daemon configuration."""
from __future__ import annotations

import os
import pathlib


def ensure_private_state_dir(path: pathlib.Path | str) -> pathlib.Path:
    state_dir = pathlib.Path(path).expanduser()
    state_dir.mkdir(parents=True, exist_ok=True)
    state_dir.chmod(0o700)
    return state_dir


def diagnose(config, state_dir: pathlib.Path | str) -> tuple[str, ...]:
    problems = []
    if not config.slack_allowlist:
        problems.append("Slack allowlist is empty")
    path = pathlib.Path(state_dir)
    if not path.exists() or path.stat().st_mode & 0o077:
        problems.append("state directory permissions must be 700")
    return tuple(problems)
