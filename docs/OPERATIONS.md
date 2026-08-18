# Operating Iris

## Health checks

Run these from the repository root:

```sh
.venv/bin/python -m iris.irisctl status
.venv/bin/python -m iris.irisctl verify-online
```

`status` prints the latest local runtime record. `verify-online` succeeds only
when the daemon has reported a recent Socket Mode connection. A process that
exists but has not connected is not considered healthy.

To restart the launchd job:

```sh
.venv/bin/python -m iris.irisctl restart
```

## First-line troubleshooting

| Symptom | Check | Safe response |
| --- | --- | --- |
| `Iris is not online` | `irisctl status`; inspect `~/.iris/launchd.err.log` | Restart with `irisctl restart`. Confirm the Mac has network access and is logged in. |
| Credential probe fails | `.venv/bin/python -m iris.slack_probe` | Recheck the two Keychain entries described in [Slack setup](slack-setup.md). Do not paste tokens into a terminal or chat. |
| Iris ignores a DM | Confirm it is a direct message from the Slack ID in `~/.iris/config.toml` | Correct the terminal-managed allowlist, then restart Iris. |
| Coding command cannot start | Run `projects`, then `cd <project>` | Confirm the project is beneath `projects_root` and that the selected local CLI is installed. |
| A tool call appears stuck | Reply `y` or `n` in the originating Slack thread | If no decision is received before its timeout, Iris denies it automatically. |
| Calendar smoke test denies access | Run the probe from an interactive terminal | Grant Calendar access in macOS Privacy & Security if desired, or leave the integration disabled. |

## State locations

Iris uses `~/.iris/` for private local state and `~/Library/LaunchAgents/` for
its launchd definition. Nothing in this directory needs to be checked into the
repository.

```text
~/.iris/
  config.toml          terminal-managed Slack user allowlist and project root
  runtime.json         atomic current health record
  sessions.json        local session registry
  memory.json          provenance-aware trusted memory ledger
  audit.jsonl          privacy-preserving audit log (rotated at its size bound)
  launchd.out.log      daemon standard output
  launchd.err.log      daemon standard error
```

Do not manually edit active JSON state while the daemon is running. Use Slack
commands for memory corrections/forgetting and `irisctl` for runtime control.

## Upgrade and verify

```sh
git pull --ff-only
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python -m iris.slack_probe
.venv/bin/python -m iris.irisctl restart
```

`pytest` is designed to run without a live Slack account. The credential probe
is the separate local acceptance check for the Socket Mode configuration.

## Disable or remove

To stop and remove the background launch agent without touching Keychain items,
Slack configuration, or `~/.iris/` state:

```sh
./scripts/uninstall.sh
```

To prevent future Slack control immediately, remove your Slack user ID from
`~/.iris/config.toml`, then restart or uninstall the daemon. If you need to
rotate credentials, do so in Slack, update the matching Keychain items, and
rerun the credential probe.

## Security routine

- Keep the Slack workspace private and add only deliberate Slack user IDs to
  the allowlist.
- Keep `~/.iris` private (`0700`) and do not commit its contents.
- Treat every approval prompt as an action review: read the summary before
  answering `y`.
- Use `stop` when you want a hard pause; it cannot be undone from Slack.
- Prefer read-only, revocable integrations. Add new provider permissions only
  with a deterministic test and a distinct live acceptance check.
