"""Terminal-only runtime inspection, restart, and re-arm commands."""
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess

from iris.runtime import StatusStore


def _kickstart() -> None:
    subprocess.run(
        ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/com.iris.gateway"],
        check=True,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="irisctl")
    parser.add_argument("command", choices=("status", "verify-online", "restart", "rearm"))
    parser.add_argument("--state-dir", default=str(pathlib.Path.home() / ".iris"))
    args = parser.parse_args(argv)
    state_dir = pathlib.Path(args.state_dir)
    store = StatusStore(state_dir / "runtime.json")
    if args.command == "status":
        status = store.read()
        print(status if status else "Iris is not running")
        return 0 if status else 1
    if args.command == "verify-online":
        print("Iris is online" if store.healthy() else "Iris is not online")
        return 0 if store.healthy() else 1
    if args.command == "rearm":
        (state_dir / "disarmed").unlink(missing_ok=True)
        _kickstart()
        print("Iris re-armed and restarted.")
        return 0
    _kickstart()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
