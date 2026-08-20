# Operating Iris

## Verification philosophy

Iris separates deterministic evidence from live dependency evidence. `pytest`
must prove schemas, routing, concurrency, denial behavior, state persistence, and
fake-backed integrations without requiring Slack or a model account. Separate
operator probes then verify the installed Slack, Claude/Codex, EventKit, and
public-provider surfaces that a fake cannot certify.

Do not call a capability live merely because its module exists. The expected
chain is: **production wiring → deterministic test → acceptance test → live
probe when an external dependency is involved**.

## Health checks

Run from the repository root:

```sh
.venv/bin/python -m iris.irisctl status
.venv/bin/python -m iris.irisctl verify-online
```

`verify-online` succeeds only for a recent Socket Mode heartbeat from a live
process. To restart the launchd job:

```sh
.venv/bin/python -m iris.irisctl restart
```

### Emergency stop and re-arm

Slack `stop` terminates registered coding sessions and writes
`~/.iris/disarmed`. The marker survives daemon crashes and restarts, so launch
requests remain blocked until the operator explicitly re-arms from Terminal:

```sh
.venv/bin/python -m iris.irisctl rearm
```

Do not delete the marker from Slack-facing code. Terminal-only re-arm is part of
the authority boundary.

## General agent runtime probes

The general-agent probe uses the locally authenticated Claude CLI with Iris's
isolated MCP configuration. It does not read Slack credentials or contact a
Slack workspace.

```sh
.venv/bin/python -m iris.agent_probe
```

It performs two checks:

1. a disposable MCP server exposes one fixed read and one fake mutation; Claude
   must invoke both, with the mutation denied;
2. a disposable project plus real `AgentActionServer` proves Claude can invoke
   `start_coding` through MCP, cross the local action socket, receive approval,
   and reach exactly one fake session launch with unchanged validated
   arguments. No real project or coding process is modified in this second
   check.

This probe is the live compatibility gate for the current plain-English
agent→approval-bound-coding path. Re-run it after upgrading Claude or changing
`agent_conversation.py`, `mcp_server.py`, or `agent_actions.py`.

## Claude tool-approval probes

The approval hook must remain active even though Iris disables operator settings
files with `--setting-sources ""`.

```sh
.venv/bin/python -m iris.hook_probe
bash scripts/checks/live_approval.sh
bash scripts/checks/live_deny_paths.sh
```

`hook_probe` forces one real Claude tool request and verifies the Iris
PreToolUse hook fires under subprocess isolation. `live_approval.sh` proves a
real Claude tool call is denied without a responder and allowed after approval
against a real `ApprovalServer`. `live_deny_paths.sh` exercises fail-closed
socket/protocol/timeout cases.

Production approval requests carry the exact Slack channel/thread in the child
environment and include bounded JSON tool arguments in the human-visible
summary. Bare `y`/`n` resolves the oldest request; `y <id>` / `n <id>` resolves
one exact concurrent request.

## Web and weather probes

```sh
.venv/bin/python -m iris.web_probe
.venv/bin/python -m iris.weather_probe
```

These make bounded public reads without Slack credentials. They prove provider
reachability, not Slack delivery.

## Calendar

First verify EventKit read permission:

```sh
.venv/bin/python -m iris.senses.calendar_probe
```

To also refresh upcoming events into Iris's quarantined sense store:

```sh
.venv/bin/python -m iris.senses.calendar_probe --sync
.venv/bin/python -m iris.senses.calendar_probe --sync --days 30
```

The sync stores only event identifier, start time, and title in
`~/.iris/senses.json`. Every row remains `untrusted`; ingestion does not promote
Calendar content into trusted memory or authority. Sync is operator-run and
there is no Calendar write capability.

## Slack connectivity

```sh
.venv/bin/python -m iris.slack_probe
```

This verifies Keychain credentials and outbound Socket Mode connectivity. It is
the live gate for the transport, not for model/tool behavior.

## Deterministic test and structural gates

Run all of these before treating a branch as releasable:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/checks/wiring_audit.py
.venv/bin/python scripts/checks/wiring_audit.py \
  --check-docs README.md docs/ARCHITECTURE.md docs/OPERATIONS.md
.venv/bin/python scripts/checks/mermaid_lint.py --min 4 docs/ARCHITECTURE.md
.venv/bin/python scripts/checks/link_check.py
```

The acceptance suite includes a deterministic Slack workflow that drives plain
English into `AgentActionServer`, proves no session exists while approval is
pending, routes `y <id>` through the real Slack/router path, and then verifies
one exact coding-session launch in the originating thread.

`test_master_agency.py` is intentionally a meta-gate over the production agent
action server, MCP exposure, Claude adapter, Slack acceptance path, approval
transport, launch configuration, and no-self-escalation tests. Its name should
never be widened without widening what it executes.

The wiring audit rejects unexplained modules that are unreachable from
production or a classified operator/live entry point. Its doc check requires
future-facing scaffolding such as salience, user model, outcome ledger, session
lanes, Hera memory export, and fallback translation to remain explicitly marked
as not wired.

## Mutation guard

The repository also contains a mutation manifest that deliberately damages
important safety invariants and asserts the suite catches the damage:

```sh
.venv/bin/python scripts/checks/mutation_guard.py \
  --manifest scripts/checks/mutations.yaml --assert-min 14
```

Run it after broad changes to approval, launch, grammar, memory, Slack, or
conversation boundaries. If a mutation target becomes stale after a legitimate
refactor, update the manifest rather than silently dropping the invariant.

## Codex compatibility

Iris launches Codex through `codex exec --sandbox workspace-write`. The command
line sandbox overrides a wider operator configuration. Current Iris does **not**
route individual Codex tool calls through Slack approval, and the Claude
streaming transport does not make a running Codex exec session steerable via
`@<id>`.

After a Codex CLI upgrade, run the repository's Codex smoke launch on the
operator Mac before relying on it. Treat resume/steering as unsupported until a
specific installed-version live test is added; do not infer parity from Claude's
transport.

## Menu bar indicator

`scripts/install.sh` installs the optional SwiftBar plugin
`scripts/menubar/iris.30s.sh`. It reads only `~/.iris/runtime.json` and reports
health. SwiftBar refreshes every 30 seconds; the daemon heartbeat is 20 seconds.

| Indicator | Meaning |
| --- | --- |
| Green | Connected and equivalent to `irisctl verify-online` success. |
| Orange | Starting, stale heartbeat, or unreadable runtime record. |
| Red | Recorded offline or recorded process is gone. |
| Gray | No runtime record exists. |

The indicator is read-only and does not approve, stop, or re-arm Iris.

## State locations

Iris keeps private runtime state beneath `~/.iris/`; the directory is created
mode `0700`.

```text
~/.iris/
  config.toml          terminal-managed allowlist and projects_root
  runtime.json         current daemon health record
  sessions.json        coding-session registry
  memory.json          provenance-aware trusted-memory ledger
  senses.json          optional quarantined source snapshot
  disarmed             persistent emergency-stop marker when present
  audit.jsonl          privacy-preserving append-only audit log
  approval.sock        local Claude tool-approval socket while daemon runs
  agent-action.sock    local general-agent action socket while daemon runs
  launchd.out.log      daemon standard output
  launchd.err.log      daemon standard error
```

Do not manually edit active JSON state while the daemon is running. Use Slack
memory commands, the Calendar operator sync, and `irisctl` controls.

## First-line troubleshooting

| Symptom | Check | Safe response |
| --- | --- | --- |
| Iris is not online | `irisctl status`; inspect `~/.iris/launchd.err.log` | Restart and verify network/login state. |
| Credential probe fails | `python -m iris.slack_probe` | Recheck Keychain entries; never paste tokens into chat. |
| Iris ignores a DM | Confirm DM and stable Slack ID in config | Correct terminal-managed allowlist and restart. |
| Coding action says gateway is disarmed | Check for `~/.iris/disarmed` | Re-arm only with `irisctl rearm` when intentional. |
| Agent cannot start requested project | Run `projects` | Use a project beneath `projects_root`; ambiguous names are denied. |
| Approval appears stuck | Inspect the approval ID in its originating thread | Reply `y <id>` or `n <id>`; timeout denies automatically. |
| Calendar sync fails | Run probe without `--sync` interactively | Grant EventKit permission if desired, then retry sync. |
| Agent probe fails after CLI upgrade | Re-run `hook_probe` and inspect installed CLI behavior | Keep the feature draft/not releasable until live compatibility is restored. |

## Upgrade and verify

```sh
git pull --ff-only
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python scripts/checks/wiring_audit.py
.venv/bin/python -m iris.agent_probe
.venv/bin/python -m iris.hook_probe
.venv/bin/python -m iris.slack_probe
.venv/bin/python -m iris.irisctl restart
.venv/bin/python -m iris.irisctl verify-online
```

For approval/launcher changes also run `live_approval.sh` and
`live_deny_paths.sh`. For Calendar changes run the EventKit probe and an
operator-authorized `--sync`. For Codex changes run its smoke launch on the same
installed CLI version that production will use.

## Disable or remove

```sh
./scripts/uninstall.sh
```

This removes Iris's launch agent and menu indicator while leaving Keychain
credentials and `~/.iris/` data in place. Removing the Slack user ID from
`config.toml` and restarting is the immediate way to revoke Slack control.

## Security routine

- Keep the Slack workspace private and the allowlist minimal.
- Keep `~/.iris` private and never commit it.
- Read exact approval summaries before answering; use indexed approval when
  more than one action is pending.
- Use `stop` for a hard pause and `irisctl rearm` only after deciding to restore
  consequential authority.
- Prefer read-only, revocable integrations. Every new write/action domain gets a
  narrow schema, daemon-owned validation, an explicit authority policy,
  deterministic tests, and a separate live gate.
- Re-run live probes after upgrading `claude`, `codex`, macOS/EventKit, or Slack
  dependencies because offline fakes cannot certify changed external contracts.
