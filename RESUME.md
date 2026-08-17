# Resume after terminal restart

Full Disk Access was granted 2026-08-17 but macOS only applies TCC grants to
**newly launched** processes, so the terminal had to be quit and reopened.

## Restart

```bash
cd "/Users/randyren/Developer/remote control"
claude --continue
```

## First thing to check

FDA should now work. If this prints a count, CP-1.1 and CP-1.2 are unblocked:

```bash
python3 -c "import sqlite3,pathlib; p=pathlib.Path.home()/'Library/Messages/chat.db'; print(sqlite3.connect(f'file:{p}?mode=ro',uri=True).execute('select count(*) from message').fetchone()[0])"
```

If it still fails, FDA was granted to the wrong binary. It must cover the
process that actually opens the file — the terminal app, and/or
`/opt/homebrew/opt/python@3.13/libexec/bin/python3`.

## State at restart

Checkpoint state lives in `.checkpoints/state.json` (gitignored, survives).

| Checkpoint | State |
|---|---|
| CP-1.1 chat.db readable | pending — was blocked on FDA, retry first |
| CP-1.2 AppleScript send | pending — sending PROVEN, needs chat.db receipt assertion |
| CP-1.3 Remote Control link | PASSED — A3 disproven, link IS retrievable |
| CP-1.4 stay awake | PASSED — `caffeinate -i -s` in the launchd job |
| CP-2.0 – CP-2.5 | PASSED — trust tiers, memory-poisoning hole closed |
| CP-2.6 Hera regression | pending — was mid-run in background, just re-run it |

```bash
python3 scripts/checkpoint_runner.py status
python3 scripts/checkpoint_runner.py run CP-1.1
python3 scripts/checkpoint_runner.py run CP-2.6   # takes several minutes
```

## Next steps, in order

1. **CP-1.1** — should pass immediately now that FDA is live.
2. **CP-1.2** — `spikes/send_imessage.sh` is fixed and verified sending. Two
   probes were already delivered to `+18254313285`. The only missing piece is
   `assert_sent.py` confirming the row in `chat.db`.
3. **CP-2.6** — re-run; it passed twice when invoked directly and failed once
   under the runner, so treat any failure as possibly flaky and read the log at
   `$CLAUDE_JOB_DIR/tmp/hera-e2e-cp26.log`.
4. **P3** — unblocked once CP-1.1 passes. Start with CP-3.1, the fake-`chat.db`
   harness; it is what makes the remaining ~30 checkpoints runnable without a
   phone.

## Carry these into P4.5 (found at CP-1.3, easy to forget)

- `CLAUDE_CODE_CHILD_SESSION` suppresses session registration entirely — a
  session spawned from inside another Claude Code session never writes
  `~/.claude/sessions/<pid>.json`. The launcher must scrub `CLAUDE*` from the
  child environment.
- A first-run **workspace-trust prompt** blocks startup in any untrusted
  directory. A daemon spawning sessions across arbitrary projects will hang.
- `--remote-control <name>` is **not** the display name; the name is derived
  from cwd. Key the session registry on **pid**, never on the name passed.
- The link is `https://claude.ai/code/<bridgeSessionId>`, read from
  `~/.claude/sessions/<pid>.json` a few seconds after launch. `spikes/rc_link.py`
  polls for it and exits 1 with a diagnostic if it never appears.

## Open decisions (see PLAN.md §8 and the end of the last session)

1. `e2e_inject.sh`'s failure message is misleading — it reports a ranking bug
   when the real cause is a skipped clean-state precondition. Adding an explicit
   precondition assertion strengthens it, but edits a test, so it needs a human
   decision.
2. `team.db has no pages` is an unmet environment precondition (no
   `team-staging/`, no `HERA_TEAM_REMOTE`, empty bare fixture repo). Real gap in
   Hera's coverage; out of scope for Iris.

## Safety net

`/Users/randyren/Developer/second brain/hera/hera.db.pre-trust-backup` is the
pre-migration database. Keep it until the trust-tier work is proven in daily
use. The live vault was verified intact throughout (58 pages, all `trust='self'`).
