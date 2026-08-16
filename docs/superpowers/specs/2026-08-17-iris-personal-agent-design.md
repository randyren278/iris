# Iris — Personal Agent System Design

**Date:** 2026-08-17
**Status:** Draft for review
**Scope:** Full-system architecture across five sub-projects

---

## 1. Thesis

> **Hera is a hippocampus with no mouth. Poke is a mouth with no hippocampus. Iris is the missing middle.**

Poke (Interaction Co., acquired by Cognition July 2026) is the closest commercial
attempt at a texting-first personal agent. Reviews converge on a structural, not
incidental, failure:

> "Poke is excellent at the last mile, which is telling you something. It is much
> weaker in the part before that: knowing what's worth telling you, and holding on
> to the things you decided last Tuesday."

Measured failure modes: ~7/10 nudge accuracy (≈30% noise), timezone/date errors,
and — decisively — **no searchable memory layer**. Information vanishes into text
threads. The reviewers' summary: *"messaging is an excellent notification channel
but fails as a central hub for information management."*

The Hera vault already solves the memory half, and solves it better than any
comparable open-source agent:

| Capability | Hera | Hermes Agent | OpenClaw | Poke |
|---|---|---|---|---|
| Keyword search over history | ✅ BM25/FTS5 | ✅ FTS5 | partial | ❌ |
| Dense/semantic retrieval | ✅ built-in | ⚠️ optional Tier 3 | ⚠️ retrieval-style | ❌ |
| Fused ranking (RRF) | ✅ k=60 | ❌ | ❌ | ❌ |
| **Usage-based ranking** | ✅ citation scoring | ❌ | ❌ | ❌ |
| **Contradiction detection** | ✅ ADR-09/10/11 | ❌ | ❌ | ❌ |
| Stable addressing | ✅ ULID | ❌ | ❌ | ❌ |
| Reversible lifecycle | ✅ prune→archive | ❌ | ⚠️ compaction | ❌ |

Citation scoring and contradiction detection are the two differentiators, and they
map exactly onto Poke's two named failures. Iris exists to give that memory a
mouth, senses, and judgment about when to speak.

---

## 2. Non-goals

- **Not building an agent runtime.** Claude Code already provides tools, hooks,
  skills, subagents, MCP, permission modes, session persistence, background
  agents, and remote control. Hermes' own documentation concedes Claude Code
  outperforms it for focused single-project work. Adopting Hermes or OpenClaw
  wholesale means inheriting a weaker runtime to obtain a channel gateway.
- **Not replacing Hera.** Hera is the memory layer, extended not rewritten.
- **Not a multi-user or team product.** Single operator. No admin console, SSO,
  or tenancy. (Hera's existing team-space feature is orthogonal and untouched.)
- **Not cloud-hosted.** Everything runs on the operator's Mac.
- **Not 16 channels.** iMessage first. Others only if they earn their place.

---

## 3. Prior art and what we take from it

### From OpenClaw
- **Declarative channel→agent binding rules.**
  `bindings: [{ agentId: "home", match: { channel: "imessage", accountId: "..." } }]`
- **Serialized execution per session lane.** Prevents race conditions and
  transcript corruption when messages arrive concurrently. Non-obvious and
  load-bearing.
- **Agent isolation:** separate workspaces, isolated auth profiles, private
  transcripts, per-agent policy.
- **Graduated sandbox levels:** `off` / `non-main` / `all`, with tools flagged
  `elevated` always executing on the host — an explicit, auditable escape hatch
  rather than an implicit one.
- **`memory/YYYY-MM-DD.md` daily append-only files** alongside curated long-term
  memory.
- **Pre-compaction memory flush** — the agent writes durable notes *before*
  context compression. Hera has SessionEnd filing but no pre-compaction sibling;
  this is a direct, cheap upgrade.
- **Secure defaults:** loopback bind, token auth required for non-loopback,
  `dmPolicy: "pairing"` for unknown contacts, `700` on state directories.
- **Operational commands:** `doctor`, `security audit --fix`, `sandbox explain`.

### From Hermes Agent
- **Deterministic Tier-1 memory.** Small, always-loaded, guaranteed-in-context
  state (`USER.md`/`MEMORY.md`, ~3.5KB) preferred over probabilistic retrieval for
  high-signal facts. Hera is currently *all* probabilistic; it needs a Tier 1.
- **Self-authored skills.** Repeated multi-step workflows get encoded as reusable
  Markdown skill files. Reported ~40% reduction in tokens and wall-clock on
  repeat tasks after 20+ skills. Auto-generated skills are drafts requiring human
  review.
- **Cron scheduler** for offline/proactive execution with async delivery to a
  messaging channel.

### From security literature
- **Dual LLM pattern** (Willison, 2023): a Privileged LLM (P-LLM) orchestrates and
  holds tool access; a Quarantined LLM (Q-LLM) processes untrusted content and has
  **no tools**. Untrusted tokens never enter P-LLM context — only symbolic
  references to Q-LLM outputs.
- **CaMeL** (Google DeepMind): extends Dual LLM with *capabilities* — metadata
  attached to values — constraining both control flow and data flow. 67%
  mitigation on the AgentDojo benchmark.
- **ClawHavoc** (January 2026): real-world OpenClaw compromise. Malicious skills
  harvested API keys, injected keyloggers, and **wrote malicious content into
  memory files for persistence across sessions.**

### What we explicitly reject
- Running OpenClaw or Hermes as the host process. Inherits their security surface
  and their release cadence.
- Input filtering as the primary injection defense. The OpenClaw hardening guide
  is right that this belongs in tool policy and sandboxing, not regex.

---

## 4. Architecture

```
        ┌──────────────────────────────────────────────┐
        │  CHANNELS                                     │
        │  iMessage · voice · web UI · push · terminal  │
        └───────────────────┬──────────────────────────┘
                            │  (no inbound network — see §4.1)
                ┌───────────▼────────────┐
                │       GATEWAY          │   NEW — project 1
                │  allowlist · grammar   │
                │  session lanes (ser-   │
                │  ialized) · approvals  │
                │  audit log             │
                └──┬──────────────────┬──┘
                   │                  │
     ┌─────────────▼──────┐   ┌───────▼─────────────────┐
     │  SALIENCE ENGINE   │   │  CLAUDE CODE SESSIONS   │
     │  NEW — project 4   │   │  runtime (existing)     │
     │  what's worth      │   │  per-project, isolated  │
     │  saying, when      │   │  P-LLM tier             │
     └─────────┬──────────┘   └───────┬─────────────────┘
               │                      │
               │      ┌───────────────▼──────────────┐
               │      │  QUARANTINE (Q-LLM)          │  NEW — project 5
               │      │  untrusted content, no tools │
               │      └───────────────┬──────────────┘
               │                      │ symbolic refs only
        ┌──────▼──────────────────────▼──────────────┐
        │  HERA — memory (existing + projects 2,3)    │
        │  hybrid search · citation rank · conflicts  │
        │  + trust tiers · user model · temporal      │
        └──────────────────────────────────────────────┘
                            ▲
        ┌───────────────────┴──────────────────────────┐
        │  SENSES — project 3                           │
        │  Gmail · Calendar · Drive · GitHub · web      │
        │  ALL untrusted → quarantine path              │
        └───────────────────────────────────────────────┘
```

### 4.1 Why iMessage as primary transport

**There is no inbound network connection.** The gateway reads a local SQLite file
(`~/Library/Messages/chat.db`) and shells out to AppleScript. Apple's
infrastructure is the transport. Consequences:

- No port forwarding, tunnel, VPN, or public auth surface
- No client app to install; works on iPhone, Apple Watch, CarPlay, Mac
- Push notifications for free
- Directly satisfies OpenClaw's own hardening advice (loopback-only posture)

Verified on the target machine: macOS 26.5.2, `chat.db` present and live
(991 MB, actively written). Reading requires a one-time **Full Disk Access**
grant; without it, reads return `authorization denied`.

---

## 5. Security architecture

Day-one requirement, not a later phase. Four mechanisms.

### 5.1 Trust tiers on memory

Every Hera page carries a `trust` field in frontmatter:

| Tier | Source | May be injected into a privileged session? |
|---|---|---|
| `self` | Operator-authored, terminal-ingested, own sessions | ✅ yes |
| `team` | Teammates' published pages | ⚠️ yes, attributed and clearly delimited |
| `untrusted` | Email bodies, web pages, messages from third parties, tool output | ❌ **never** |

`prompt_inject.py` filters on `trust` before formatting. This is the single
highest-value change in the whole spec.

> **Why this is urgent:** `prompt_inject.py:131` currently reads
> `# Format as factual statements (not imperatives) to sidestep injection defenses (R-8).`
> Vault content is deliberately phrased to bypass the model's own injection
> defenses. Correct while all content is operator-authored; a critical
> vulnerability the instant untrusted content is ingested. This must land
> **before** project 3, not with it.

### 5.2 Dual-LLM quarantine

Untrusted content never enters a tool-holding context.

```
email arrives
  └─► Q-LLM (no tools, no shell, no network, no memory writes)
        └─► emits STRUCTURED output only:
              { sender_ref: "$e1", subject_ref: "$e2",
                intent: "meeting_request", urgency: 3,
                proposed_times: ["$e3"] }
        └─► raw body → Hera at trust:untrusted, addressable by ULID
  └─► P-LLM sees ONLY the structured record + refs. Never the body.
        └─► if the operator explicitly asks to read it, the body is shown
            to the *operator*, still never re-entering P-LLM context.
```

Structured schemas are enumerated and validated. A Q-LLM that emits anything
off-schema fails closed.

### 5.3 Capability tags (CaMeL-lite)

Values carry provenance metadata. Policy is enforced at the tool boundary, not by
prompting:

- A value tagged `origin:untrusted` may not become a `Bash` argument, a file path,
  a URL, or a recipient address.
- A value tagged `origin:untrusted` may not be written to a `trust:self` page.
- Violations fail closed and are logged as security events.

Full CaMeL is a research system; the tractable subset is provenance tags plus a
small enforced policy table at the tool boundary.

### 5.4 Operational controls

- **Sender allowlist**, exact-match, single handle. Mutable *only* from the
  terminal — never from an incoming message. (Taken directly from Anthropic's
  official `imessage` plugin, which already implements this.)
- **Approval gating** via `PreToolUse` hook (§6.1).
- **Append-only audit log** of every message, decision, tool call, and approval.
- **Kill switch:** one text (`stop`) halts all sessions and disarms the gateway.
- **Skills are code.** ClawHavoc's payload arrived as a skill. Auto-generated
  skills (§6.5) land in a `drafts/` directory and require terminal review before
  becoming loadable.
- **Secrets** never enter agent context; state dir `700`; no plaintext tokens.

---

## 6. Components

### 6.1 Gateway (`irisd`) — project 1

Python daemon under `launchd`. Owns all channel I/O and routing state.

**Responsibilities**
- Poll `chat.db` every 2s (read-only URI, WAL-safe) for new rows from allowlisted handles
- Parse against the command grammar; fall back to LLM translation (below)
- Maintain the session registry
- Serialize execution **per session lane** (OpenClaw's lesson: one in-flight turn
  per lane, queue the rest)
- Send outbound via AppleScript
- Host the approval queue

**Grammar** — deterministic, covers the common path:

```
ls | projects            list projects under ~/Developer
cd <fuzzy>               fuzzy-match, set active project
claude <prompt>          launch/continue Claude Code in active project
codex <prompt>           same for Codex
sessions                 1 ✓ remote-control · 2 ⏳ hera (awaiting approval)
@2 <prompt>              address session 2
link                     Remote Control link for active session
y | n                    answer pending approval
kill <n>
stop                     kill switch — halt everything
```

**LLM fallback.** Unmatched input goes to `claude -p --json-schema` on a cheap
model with the grammar in the prompt. It returns a *proposed* command; the gateway
replies `did you mean: cd remote-control? [y/n]`. **The fallback model never
executes anything** — it only translates, and the operator confirms. This is what
makes the hybrid safe.

**Output policy.** Short status inline; anything long (diffs, plans, errors) is
summarized with a Remote Control link so the operator escalates into the real
mobile UI. Text stays skimmable. Threshold is a single tuning knob.

**Approvals.** Worker sessions run `--permission-mode manual` with a `PreToolUse`
hook that POSTs to `irisd`. The gateway texts the pending tool call and blocks;
`y` allows, `n` denies, timeout denies. Uses documented hook machinery rather than
scraping stdout.

**Session registry** (`~/.iris/sessions.json`): `id`, `tool`, `cwd`, `session_id`,
`remote_control_name`, `lane`, `state`, `last_activity`, `trust_policy`.

### 6.2 Hera extensions — project 2

1. **Trust tiers** (§5.1) — frontmatter field, index column, inject-hook filter.
   *Ships first, ahead of everything else.*
2. **User model.** Tier-1 deterministic memory, Hermes-style but as real pages:
   `wiki/self/preferences.md`, `people.md`, `routines.md`, `standing-decisions.md`.
   Always loaded, never retrieved probabilistically. Small and curated.
3. **Temporal retrieval.** "What did I decide Tuesday" requires time-aware query.
   Add `decided_at` to pages and a decision-log view; extend `hybrid_search` with
   an optional time filter.
4. **Non-coding-channel writes.** Texts, calls, and emails become memories. Today
   only Claude Code sessions get filed.
5. **Pre-compaction flush.** Write durable notes before context compression
   (OpenClaw's pattern; complements existing SessionEnd filing).
6. **Entity resolution.** The "Randy" in an email is the "Randy" in a note. Hera
   has ULIDs and entity pages already; this is a merge/alias layer.

### 6.3 Senses — project 3

Gmail, Google Calendar, and Google Drive MCPs are **already connected** in the
operator's environment. Plus GitHub/Linear, browser history, clipboard, location
(via Shortcuts), and `agent-reach` (already installed — 15 platforms).

**Every sense is untrusted input** and routes through §5.2 without exception.
Ingestion turns the inbox into searchable memory, which is precisely Poke's
worst failure.

### 6.4 Salience engine — project 4

**The differentiator.** Poke shipped 7/10 and that is why it is annoying.

- **Scored nudges.** Every proactive message is scored on outcome: acted on /
  replied to / ignored / explicitly rejected. This is *structurally the same
  mechanism as Hera's citation scoring* — the vault already learns which pages are
  useful from behavior. Extend it to learn which nudges are worth sending.
- **Interrupt budget.** Max N interruptions per day. Candidates are ranked;
  everything below the line goes into a digest instead of a notification.
- **Quiet hours** and channel-appropriate urgency.
- **Cron/scheduled tasks** (Hermes pattern): morning digest, stale-PR watch,
  keyword monitoring.

Requires projects 1–3 to exist. Do not attempt earlier.

### 6.5 Voice and self-improvement — project 5

- Local Whisper for dictation; TTS replies. Dictate while walking.
- Self-authored skills from repeated patterns (Hermes). Drafts only, terminal
  review required (§5.4).
- Feedback loop: Hera's memory schema already defines `type: feedback` with
  **Why** and **How to apply** fields — a learning loop that is already half
  specified.

---

## 7. Project sequence

| # | Project | Depends on | Done when |
|---|---|---|---|
| 0 | **Trust tiers + spikes** | — | Inject hook filters by trust; chat.db read, AppleScript send, and RC-link retrieval all verified |
| 1 | **Gateway + launcher** | 0 | Text `cd x` then `claude <task>` from the phone, get a link back, approve a tool call by replying `y` |
| 2 | **Hera as agent memory** | 0 | User model loads deterministically; "what did I decide Tuesday" returns the decision |
| 3 | **Senses** | 1, 2 | Email is searchable in Hera at `trust:untrusted`; no untrusted content reaches a privileged session (verified by test) |
| 4 | **Salience engine** | 1–3 | Nudge precision measurably beats Poke's ~7/10 over a 2-week window |
| 5 | **Voice + self-improvement** | 1–4 | Dictate a task while walking; agent proposes a skill after a repeated workflow |

Project 1 is standalone-useful within roughly a week. Project 0 is small and
gates everything.

---

## 8. Risks and open questions

| Risk | Severity | Mitigation |
|---|---|---|
| **Remote Control link not retrievable programmatically** | Medium | Unverified. Spike in project 0. Fallback: text the session *name*; operator picks it in the app. Degrades UX, not viability. |
| **Mac sleeps → nothing works** | High | Hard prerequisite. `pmset` shows `sleep 1` on battery, standby on AC. Requires `caffeinate -s` under the same launchd job, or pmset changes. Not a feature — a precondition. |
| **AppleScript→Messages send reliability on macOS 26** | Medium | Historically flaky across releases. 5-minute spike in project 0. |
| **Memory poisoning** | **High** | §5.1 trust tiers + §5.3 capability tags. The named ClawHavoc persistence mechanism. |
| **Prompt injection via senses** | **High** | §5.2 dual-LLM quarantine. |
| **Salience never beats 7/10** | Medium | Genuinely hard; Poke had a funded team. Mitigation is the scoring loop, but this is the most likely project to disappoint. Interrupt budget limits the downside even if precision stays mediocre. |
| **`codex remote-control` is experimental** | Low | Expect the pairing flow to change. Isolate behind an adapter. |
| **Auto-generated skills as attack vector** | Medium | Drafts directory + terminal review (§5.4). |

**Open questions**
1. Can the Remote Control link be obtained outside the session? (blocks a project-1 UX detail)
2. Does the official `imessage` plugin expose anything reusable by a standalone
   daemon, or does `irisd` own chat.db polling directly? Current assumption: the
   latter (~80 lines), with the plugin installed for the *reverse* direction so
   worker sessions can text the operator unprompted.
3. Which model tier for the Q-LLM? Cheap and fast is fine — it only extracts
   structure — but it must fail closed on off-schema output.

---

## 9. Prerequisites

- Full Disk Access for the daemon's interpreter (System Settings → Privacy)
- Automation permission for Messages
- `caffeinate` / power settings so the Mac stays reachable
- `claude plugin install imessage@claude-plugins-official` (confirmed present in
  the operator's marketplace index)

---

## 10. Sources

- Poke reviews and failure analysis — https://blog.saner.ai/poke-reviews/
- Poke overview — https://techcrunch.com/2026/04/08/poke-makes-ai-agents-as-easy-as-sending-a-text/
- Hermes Agent architecture — https://www.aibuilderclub.com/blog/hermes-nous-research-self-improving-agent
- Hermes Agent — https://hermes-agent.org/
- OpenClaw architecture — https://medium.com/@eswar.kalakata/inside-openclaw-the-architecture-of-a-self-hosted-multi-agent-ai-gateway-5870aab11f22
- OpenClaw security hardening — https://nebius.com/blog/posts/openclaw-security
- Security, Privacy, and Ethical Risks in OpenClaw — https://arxiv.org/pdf/2605.23330
- A Security Analysis of the OpenClaw AI Agent Framework — https://arxiv.org/pdf/2603.27517
- Design Patterns for Securing LLM Agents against Prompt Injections — https://arxiv.org/pdf/2506.08837
- CaMeL / Defeating Prompt Injections by Design — https://simonwillison.net/2025/Apr/11/camel/
- Official Claude Code iMessage plugin — https://claude.com/plugins/imessage
- claude-imessage (daemon prior art) — https://github.com/dvdsgl/claude-imessage
- imessage-tools (Claude + Codex) — https://github.com/benelser/imessage-tools
