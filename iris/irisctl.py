"""Terminal-only runtime inspection and restart commands."""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

from iris.runtime import StatusStore


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="irisctl")
    parser.add_argument("command", choices=("status", "verify-online", "restart"))
    parser.add_argument("--state-dir", default=str(pathlib.Path.home() / ".iris"))
    args = parser.parse_args(argv)
    store = StatusStore(pathlib.Path(args.state_dir) / "runtime.json")
    if args.command == "status":
        status = store.read()
        print(status if status else "Iris is not running")
        return 0 if status else 1
    if args.command == "verify-online":
        print("Iris is online" if store.healthy() else "Iris is not online")
        return 0 if store.healthy() else 1
    subprocess.run(["launchctl", "kickstart", "-k", f"gui/{__import__('os').getuid()}/com.iris.gateway"], check=True)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
