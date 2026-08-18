# Iris architecture

Iris is a local, single-operator Slack gateway. Its architecture optimizes for
three properties: clear authority boundaries, recovery after a laptop sleeps,
and evidence that the safety path still holds without a live Slack account.

## Runtime

`launchd` starts `python -m iris.main` when the operator logs in. A runtime
supervisor owns a single instance lock and atomically updates
`~/.iris/runtime.json`. Its heartbeat reports `online` only after the Socket
Mode client connects; `irisctl verify-online` also rejects stale status.

The transport is Slack Socket Mode. The Mac opens the connection, receives
events, acknowledges the Socket Mode envelope, and posts thread replies through
Slack's Web API. Iris does not bind an HTTP port.

## Message routing

1. The Slack transport accepts only `message` events from a direct-message
   channel. Bot, subtype, duplicate, and malformed events are ignored.
2. The sender must be in `slack_allowlist`, a terminal-managed list of stable
   Slack user IDs. Rejected messages are audited by digest, never body text.
3. Recognized commands enter the deterministic command router. Unrecognized
   text is a conversational turn instead.
4. Every reply is posted to the original thread.

The conversation backend invokes Claude in text-only mode. Its system prompt
states that it has no tools and must not represent prose as a completed action.
The command router is the only path that can start a coding session.

## Coding sessions and approvals

Iris launches Claude Code or Codex only inside the selected project directory.
Claude Code sessions use manual permission mode. Before a tool call is allowed,
the approval hook contacts a Unix-domain socket owned by Iris. The daemon
renders the request in Slack and waits for `y` or `n`.

The flow fails closed: an unavailable socket, a malformed request, a timeout,
or a denial all return `approved: false`. `stop` terminates active sessions and
disarms the gateway; rearming is a terminal-only operation.

## Data and trust

| Data | Location | Trust / lifecycle |
| --- | --- | --- |
| Slack app and bot tokens | macOS login Keychain | never loaded from repository files, prompts, or environment variables |
| Runtime state, sessions, audit, memory | `~/.iris/` | directory is created mode `0700`; atomic state files use mode `0600` where implemented |
| Approved memory claims | `~/.iris/memory.json` | only explicitly confirmed `self` or `team` claims are retrievable |
| Corrected / forgotten claims | same memory ledger | correction adds a superseding record; forgetting replaces the record with a tombstone |
| Calendar source metadata | operator-selected local store | quarantined as `untrusted`; source revocation removes that source's stored items |
| Audit records | `~/.iris/audit.jsonl` | append-only rotation; rejected inbound text is represented only by SHA-256 digest |

Trusted context injected into a conversation may only be `self` or `team`
memory. External source material is not promoted by retrieval, scoring, or
conversation alone.

## Present maturity

The architecture deliberately contains future-facing seams, but the README
only promises enabled behavior:

- Memory is a local provenance-aware JSON ledger with correction and forget
  semantics.
- The user-model and salience modules are currently bounded scaffolding. The
  salience engine defaults to shadow mode and sends no unsolicited messages.
- Calendar is the only live sense currently wired for a macOS read-only probe.
  Tasks, documents, and email remain planned integrations.
- Capability policy is deny-by-default. A new skill can be drafted but is not
  automatically made loadable.

The delivery plans and checkpoints in [`PLAN.md`](../PLAN.md) and
[`IRIS-MASTER-PLAN.md`](../IRIS-MASTER-PLAN.md) are the source of truth for
future scope and human acceptance gates.
