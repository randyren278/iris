# Plan: Iris — Trust Tiers, Slack Gateway + Agent Launcher (v2)

Planned: 2026-08-17 · amended: 2026-08-17

## Decision record

The original iMessage-first transport has been superseded as the production
channel. On this Mac, a self-chat reply is recorded only as `is_from_me=1`, so
it cannot safely be distinguished from the gateway's own outgoing messages
without a visible command tag. A distinct iMessage identity would require a
separate Apple Account/session and does not meet the desired natural-conversation
experience on the current device.

**Slack Free + Socket Mode is now the production channel.** It provides a
distinct Iris bot identity and a normal mobile DM while keeping the Mac behind
an outbound WebSocket—no public listener, tunnel, or additional device.

The local iMessage prototype is retained as an experiment only. It must not be
installed as the production daemon or used to satisfy acceptance criteria.

## Objective

Ship a launchd-managed local daemon that lets the operator start and steer
Claude Code and Codex sessions in local projects through a private Slack DM,
with per-tool-call approval, append-only audit logging, and the completed Hera
trust-tier migration protecting privileged prompts from untrusted memory.

## Success criteria

1. In a private Slack DM with Iris, `cd <fuzzy-project-name>` then
   `claude <task>` starts a Claude Code session in that directory and returns a
   reply within 30 seconds.
2. A tool call requiring approval posts a readable Slack prompt and blocks;
   `y` allows, `n` denies, and timeout denies.
3. `stop` terminates every running session and disarms the gateway.
4. Slack events from non-allowlisted user IDs are ignored, never executed, and
   recorded in the audit log without their message body.
5. Hera's `prompt_inject.py` never injects a page whose trust is not `self` or
   `team`, proven by its planted-untrusted-page test.
6. Hera's existing e2e suite passes unchanged after the trust-tier migration.
7. The daemon starts on login via launchd and appends inbound events, parse
   decisions, launches, tool calls, approvals, denials, and errors to an
   append-only audit log.
8. The complete gateway suite passes without a Slack workspace or phone by
   using a fake Socket Mode event source and recording Slack client.

## Non-goals

- Public Slack application, multi-workspace distribution, or Slack Marketplace
  publication.
- iMessage as a primary control channel.
- Projects 2–5 from the broader Iris design (memory, senses, salience, voice).
- Multi-user administration, SSO, or a web console.

## Constraints and security invariants

- Slack Socket Mode only: the daemon makes an outbound WebSocket connection;
  it exposes no HTTP listener.
- The workspace is private. The gateway accepts only explicit Slack user IDs,
  never display names or email addresses.
- App and bot tokens are stored in the macOS Keychain; they never enter the
  repository, audit log, subprocess environment dumps, or agent prompts.
- All routing uses Slack `channel_id` and `thread_ts`, never a guessed display
  name. Every reply remains in the originating DM/thread.
- Message text from unallowlisted Slack users is not logged; only a SHA-256
  digest and minimal event metadata are recorded.
- The completed Hera migration remains a precondition for any future untrusted
  ingestion.

## Current evidence

| Area | Status | Evidence |
|---|---|---|
| Hera trust tiers | Complete | `CP-2.0` through `CP-2.6` passed in `.checkpoints/state.json` |
| Fake Messages harness / attributedBody decoder | Complete experiment | CP-3.1–3.4 passed; retained for reference only |
| iMessage live self-chat | Rejected for production | real phone replies recorded only as `is_from_me=1` |
| Slack workspace/app | Pending manual setup | required before live Socket Mode gate |

## Phase map

```text
Completed Hera trust substrate
        │
        ▼
S0 Slack provisioning ─► S1 transport skeleton ─► S2 grammar/projects
        │                                              │
        └──────────────────────────────────────────────┤
                                                       ▼
S3 registry/launchers ─► S4 lanes/approvals ─► S5 output/fallback
                                                       │
                                                       ▼
                                  S6 launchd/audit/doctor ─► FINAL (narrow gateway)
                                                       │
                                                       ▼
                         S7 always-on conversational control plane ─► M0
```

## S0 — Slack provisioning and capability spike

**Goal:** Establish one private workspace and an Iris app that can receive a
DM over Socket Mode. This is an operator-authenticated setup step.

**Manual operator actions:** create or select a private Slack workspace; create
a Slack app named Iris; enable Socket Mode and Event Subscriptions; create an
app-level token with `connections:write`; install the app with the minimal bot
scopes `chat:write`, `im:history`, and `im:read`; then start a DM with Iris.
The operator enters authentication credentials and approves Slack permissions.

**Deliverables:** `docs/slack-setup.md`, Keychain token lookup helper,
`tests/test_slack_credentials.py`.

```yaml
checkpoint:
  id: CP-S0
  phase: "Slack Socket Mode reachable"
  halt: true
  max_attempts: 3
  human_gate: true
  checks:
    - name: keychain-lookup-works
      run: ".venv/bin/python -m pytest tests/test_slack_credentials.py -q"
      expect: "exit 0"
    - name: socket-mode-authenticates
      run: ".venv/bin/python -m iris.slack_probe"
      expect: "exit 0"
    - name: dm-roundtrip-live
      run: ".venv/bin/python -m iris.slack_probe --send 'iris CP-S0 probe'"
      expect: "exit 0"
```

## S1 — Slack transport walking skeleton

**Goal:** An allowlisted Slack DM reaches the daemon and is echoed into the
same conversation. The production adapter is testable without Slack.

**Deliverables:** `iris/slack.py`, `iris/slack_config.py`, fake event source
and recording client under `tests/`, updated `iris/main.py` transport boundary.

```yaml
checkpoint:
  id: CP-S1
  phase: "Slack DM walking skeleton"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: allowlisted-dm-echoes-in-same-thread
      run: ".venv/bin/python -m pytest tests/test_slack_echo_e2e.py -q"
      expect: "exit 0"
    - name: unknown-user-is-silent
      run: ".venv/bin/python -m pytest tests/test_slack_rejects_unknown.py -q"
      expect: "exit 0"
    - name: ignores-bot-and-retries
      run: ".venv/bin/python -m pytest tests/test_slack_dedupe.py -q"
      expect: "exit 0"
    - name: no-network-listener
      run: ".venv/bin/python -m pytest tests/test_slack_no_listener.py -q"
      expect: "exit 0"
    - name: full-suite-green
      run: ".venv/bin/python -m pytest -q"
      expect: "exit 0"
```

## S2 — Grammar and project selection

**Goal:** Slack text becomes safe, deterministic commands.

**Deliverables:** pure grammar parser, project discovery and fuzzy selection.

Commands: `ls`, `projects`, `cd <x>`, `claude <p>`, `codex <p>`, `sessions`,
`@<n> <p>`, `link`, `y`, `n`, `kill <n>`, `stop`.

**Invariants:** unknown input is unparsed; ambiguous project matches never
guess; directory traversal is rejected; output is message-budgeted.

```yaml
checkpoint:
  id: CP-S2
  phase: "grammar and projects"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: grammar-is-pure-and-complete
      run: ".venv/bin/python -m pytest tests/test_grammar.py tests/test_grammar_unparsed.py tests/test_grammar_purity.py tests/test_grammar_tolerance.py -q"
      expect: "exit 0"
    - name: projects-safe-and-paginated
      run: ".venv/bin/python -m pytest tests/test_projects_list.py tests/test_projects_pagination.py tests/test_cd_match.py tests/test_cd_ambiguous.py tests/test_cd_spaces.py tests/test_cd_no_traversal.py -q"
      expect: "exit 0"
```

## S3 — Registry, launchers, and session control

**Goal:** Start Claude Code and Codex from the selected project, retain a
restart-safe session registry, and support `sessions`, `kill`, and `stop`.

**Invariants:** atomic registry writes; dead processes reaped on load; Claude
uses manual permission mode and the approval hook; `stop` kills all sessions
and disarms the gateway until terminal re-arm.

```yaml
checkpoint:
  id: CP-S3
  phase: "sessions launch and stop safely"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: registry-and-controls
      run: ".venv/bin/python -m pytest tests/test_registry.py tests/test_registry_persistence.py tests/test_registry_atomic.py tests/test_registry_reap.py tests/test_cmd_sessions.py tests/test_cmd_kill.py tests/test_cmd_stop.py tests/test_disarmed.py -q"
      expect: "exit 0"
    - name: launchers
      run: ".venv/bin/python -m pytest tests/test_launcher_interface.py tests/test_launch_claude_cwd.py tests/test_launch_claude_registry.py tests/test_launch_claude_flags.py tests/test_launch_codex_cwd.py -q"
      expect: "exit 0"
    - name: real-launch-smoke
      run: "bash tests/smoke_launch_claude.sh && bash tests/smoke_launch_codex.sh"
      expect: "exit 0"
```

## S4 — Lanes and approvals

**Goal:** Same-session Slack commands serialize, different sessions can run in
parallel, and every risky tool call waits for a Slack approval decision.

**Invariants:** approval endpoint is a Unix socket or loopback-only; daemon
unreachable denies; `y`/`n` resolve oldest pending request and indexed forms
target the selected request; timeout denies and notifies.

```yaml
checkpoint:
  id: CP-S4
  phase: "serialized lanes and approvals"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: lanes
      run: ".venv/bin/python -m pytest tests/test_lane_serial.py tests/test_lane_parallel.py tests/test_lane_burst_order.py -q"
      expect: "exit 0"
    - name: hook-and-approval-flow
      run: ".venv/bin/python -m pytest tests/test_hook_blocks.py tests/test_hook_fail_closed.py tests/test_hook_long_block.py tests/test_approval_yes.py tests/test_approval_no.py tests/test_approval_indexed.py tests/test_approval_rendering.py tests/test_approval_timeout.py tests/test_approval_timeout_notify.py -q"
      expect: "exit 0"
```

## S5 — Output policy and fallback translator

**Goal:** Keep Slack replies readable; unparsed natural language becomes a
proposal, never an action.

**Invariants:** bounded message count; no mid-word split; translator has no
tools; schema failure is rejected; proposal requires an explicit confirmation
and expires.

```yaml
checkpoint:
  id: CP-S5
  phase: "output and fallback fail closed"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: output-policy
      run: ".venv/bin/python -m pytest tests/test_output_short.py tests/test_output_long.py tests/test_output_burst_cap.py -q"
      expect: "exit 0"
    - name: proposals-never-execute-directly
      run: ".venv/bin/python -m pytest tests/test_fallback_translate.py tests/test_fallback_no_tools.py tests/test_fallback_off_schema.py tests/test_fallback_never_executes.py tests/test_proposal_confirm.py tests/test_proposal_expiry.py -q"
      expect: "exit 0"
```

## S6 — Daemon, audit, and security doctor

**Goal:** Iris starts on login, reconnects Socket Mode, writes an auditable
history, and reports unsafe configuration.

**Invariants:** state directory `700`; audit log append-only with rotation;
tokens/message bodies from rejected users absent; no non-loopback listener;
launchd KeepAlive restarts the daemon.

```yaml
checkpoint:
  id: CP-S6
  phase: "operable and auditable daemon"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: launchd-lifecycle
      run: "bash scripts/install.sh && bash scripts/install.sh && bash tests/test_keepalive.sh && bash scripts/uninstall.sh"
      expect: "exit 0"
    - name: audit-and-doctor
      run: ".venv/bin/python -m pytest tests/test_audit_coverage.py tests/test_audit_append_only.py tests/test_audit_rotation.py tests/test_audit_no_secrets.py tests/test_doctor_detects_bad_perms.py tests/test_doctor_empty_allowlist.py tests/test_slack_no_listener.py -q"
      expect: "exit 0"
```

## Final checkpoint

```yaml
checkpoint:
  id: CP-FINAL
  phase: "Slack end-to-end acceptance"
  halt: true
  max_attempts: 2
  human_gate: true
  checks:
    - name: launch-from-slack
      run: ".venv/bin/python -m pytest tests/acceptance/test_sc1_launch.py -q"
      expect: "exit 0"
    - name: approval-flow
      run: ".venv/bin/python -m pytest tests/acceptance/test_sc2_approval.py -q"
      expect: "exit 0"
    - name: stop-and-allowlist
      run: ".venv/bin/python -m pytest tests/acceptance/test_sc3_stop.py tests/acceptance/test_sc4_allowlist.py -q"
      expect: "exit 0"
    - name: hera-regression
      run: "bash scripts/hera_e2e_scratch.sh"
      expect: "exit 0"
    - name: fake-suite-green
      run: ".venv/bin/python -m pytest -q"
      expect: "exit 0"
    - name: live-slack-dm
      run: ".venv/bin/python -m iris.slack_probe --acceptance"
      expect: "exit 0"
```

## S7 — Always-on conversational control plane

**Why this additional slice exists:** CP-FINAL proves the original narrow
gateway contract, but it does not prove that Iris is a useful conversational
agent. The operator requires Iris to be available whenever this laptop is
awake, respond naturally in Slack, return coding-agent results in the same
thread, and genuinely steer an existing session. S7 is therefore required
before M0 approval; it does not reinterpret CP-FINAL's already-recorded
evidence.

**Goal:** Run one observable, self-recovering Iris daemon whenever the Mac is
logged in and awake. A normal allowlisted DM receives a bounded agentic reply;
operational commands remain explicit; coding sessions stream meaningful
progress and their final result to the originating Slack thread.

**Operating model (adapted from the Straits harvester):** launchd owns the
long-lived process (`RunAtLoad`, `KeepAlive`, and a throttle to prevent crash
loops). The daemon writes an atomically replaced private status record with
PID, boot ID, Socket Mode connection state, last inbound/outbound timestamps,
and last error class. A small `irisctl status|restart` command reads it and
uses `launchctl`; a stale heartbeat or disconnected socket is unhealthy rather
than silently "running." A single-instance lock prevents a manual start from
creating a second Socket Mode consumer, and stale-lock recovery is age-first
so a sleep/crash cannot wedge the service. Sleep is expected; after wake the
daemon reconnects and status returns online without replaying old events.

**Conversation and safety model:**

- The command grammar remains the deterministic control plane for project
  selection, sessions, approval decisions, `stop`, and diagnostics.
- All other allowlisted messages enter a per-DM conversation coordinator. It
  preserves bounded turn context, labels retrieved memory by trust/provenance,
  and asks a local coding-agent backend for text only. It never treats model
  text as an executable command.
- The coordinator may propose an operation, but a typed capability dispatcher
  performs it only after the existing explicit approval policy permits it.
- A coding session has a durable transport endpoint: its launch prompt,
  subsequent `@<id> ...` turns, structured progress, final result, and failure
  all map to the same Slack thread. Acknowledging a queued follow-up without
  delivering it is forbidden.
- Output is streamed in message-budgeted updates and includes a terminal
  result/error state. Raw tool inputs and secrets stay out of Slack and audit
  records.

**Deliverables:** `iris/runtime/` daemon supervisor and atomic status store;
`iris/conversation/` turn coordinator and bounded context policy;
`iris/session_transport/` Claude/Codex adapters with bidirectional session
input and structured output; `iris/irisctl.py`; launchd installer/uninstaller
with logs and self-check; fake agent/event sources; live runbook.

```yaml
checkpoint:
  id: CP-S7
  phase: "always-on conversational Iris"
  halt: true
  max_attempts: 3
  human_gate: true
  checks:
    - name: daemon-supervision-and-wake-recovery
      run: ".venv/bin/python -m pytest tests/test_runtime_status.py tests/test_runtime_single_instance.py tests/test_runtime_stale_lock.py tests/test_runtime_reconnect.py tests/test_launchd_daemon.py -q"
      expect: "exit 0"
    - name: natural-conversation-is-safe-and-contextual
      run: ".venv/bin/python -m pytest tests/test_conversation_turns.py tests/test_conversation_context.py tests/test_conversation_untrusted.py tests/test_conversation_no_implicit_actions.py -q"
      expect: "exit 0"
    - name: coding-session-results-and-steering-reach-the-same-thread
      run: ".venv/bin/python -m pytest tests/test_session_streaming.py tests/test_session_steering.py tests/test_session_terminal_result.py tests/test_session_output_budget.py -q"
      expect: "exit 0"
    - name: approvals-are-delivered-to-the-originating-thread
      run: ".venv/bin/python -m pytest tests/test_approval_slack_delivery.py tests/test_approval_fail_closed.py -q"
      expect: "exit 0"
    - name: full-fake-suite-green
      run: ".venv/bin/python -m pytest -q"
      expect: "exit 0"
    - name: live-jarvis-acceptance
      run: ".venv/bin/python -m iris.slack_probe --jarvis-acceptance"
      expect: "exit 0"
```

## Execution protocol

1. Run checkpoint checks exactly as written with `scripts/checkpoint_runner.py`.
2. On a failure, fix the implementation and rerun the entire checkpoint.
3. Human gates require explicit operator confirmation after the automated
   checks pass.
4. A checkpoint’s passing result is evidence only for its stated scope.
   Final completion requires every final-check result plus a real Slack DM.
