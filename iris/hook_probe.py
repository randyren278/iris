"""Live acceptance probe: Iris's approval hook must fire under isolation.

Iris passes both `--setting-sources ""` (load no settings files, so operator
hooks cannot reach an Iris subprocess) and `--settings <json>` (install Iris's
own PreToolUse approval hook). If the first ever suppressed the second, tool
calls would stop being mediated silently — the worst failure this boundary has.
This probe proves it does not, by making a real Claude call that must attempt a
tool and asserting the hook ran.

Run it like the other live checks, and never in the deterministic suite:

    .venv/bin/python -m iris.hook_probe
"""
from __future__ import annotations

import json
import pathlib
import shlex
import subprocess
import sys
import tempfile

from iris.conversation import CLAUDE_ISOLATION, CONVERSATION_MODEL

TIMEOUT = 180


def probe() -> int:
    with tempfile.TemporaryDirectory(prefix="iris-hook-probe-") as workspace:
        directory = pathlib.Path(workspace)
        sentinel = directory / "hook-fired"
        # Deny every tool call and record that we were consulted. Exit 2 is how
        # a PreToolUse hook blocks a call, mirroring iris.approval_hook.
        hook = directory / "hook.sh"
        hook.write_text(
            "#!/bin/bash\n"
            f"touch {shlex.quote(str(sentinel))}\n"
            'echo "denied by the Iris hook probe" >&2\n'
            "exit 2\n"
        )
        hook.chmod(0o700)
        settings = json.dumps(
            {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
                {"type": "command", "command": str(hook)}]}]}},
            separators=(",", ":"),
        )
        command = ["claude", "--model", CONVERSATION_MODEL, "--permission-mode", "manual",
                   *CLAUDE_ISOLATION, "--settings", settings, "-p",
                   f"Create a file called probe.txt in {workspace} using the Write tool."]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT,
                                    cwd=workspace, check=False)
        except FileNotFoundError:
            print("claude CLI not found on PATH", file=sys.stderr)
            return 1
        except subprocess.TimeoutExpired:
            print(f"claude did not answer within {TIMEOUT}s", file=sys.stderr)
            return 1

        if sentinel.exists():
            print("Approval hook fired under --setting-sources '' — tool calls stay mediated.")
            return 0

        print("APPROVAL HOOK DID NOT FIRE. Tool calls may be unmediated under isolation.",
              file=sys.stderr)
        print(f"claude exited {result.returncode}", file=sys.stderr)
        # The transcript can echo the prompt but never a credential; the command
        # itself carries only flags and a temp path.
        print(f"stderr: {result.stderr.strip()[:500]}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - live probe entry point
    raise SystemExit(probe())
