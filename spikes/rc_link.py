#!/usr/bin/env python3
"""CP-1.3 spike: retrieve a Remote Control link from outside the session.

    python3 spikes/rc_link.py <pid> [--timeout 60]

Claude Code writes ~/.claude/sessions/<pid>.json for every live session. When
the session was started with `--remote-control`, that file gains a
`bridgeSessionId` once the bridge connects; the shareable link is
https://claude.ai/code/<bridgeSessionId>. The id is NOT in `claude agents
--json`, so this file is the only external source.

The bridge connects a few seconds after launch, hence the poll.
"""
import argparse
import json
import pathlib
import sys
import time

SESSIONS = pathlib.Path.home() / ".claude/sessions"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pid", type=int, help="pid of the claude process")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()

    path = SESSIONS / f"{args.pid}.json"
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            data = {}
        bridge = data.get("bridgeSessionId")
        if bridge:
            print(f"https://claude.ai/code/{bridge}")
            return 0
        time.sleep(1)

    sys.stderr.write(
        f"no bridgeSessionId in {path} after {args.timeout}s "
        f"(was the session started with --remote-control?)\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
