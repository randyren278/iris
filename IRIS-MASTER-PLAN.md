# Plan: Iris — Long-Term Personal Intelligence

Planned: 2026-08-17 · Executor protocol: v1 (embedded below, binding)

## Objective

Build Iris into a local-first, continuously improving personal intelligence
that compounds trusted understanding of its operator while safely coordinating
their projects, information, and approved actions over years.

## Success criteria (re-verified by CP-MASTER-FINAL)

1. An operator can hold a natural Slack DM conversation with Iris, launch and
   steer a Claude Code or Codex session, and receive a result in the same DM.
2. Iris retains operator-approved facts, project decisions, and conversation
   outcomes with provenance; corrections supersede prior facts without erasing
   their history.
3. Only `self` and explicitly attributed `team` memory can enter privileged
   agent context; untrusted material remains non-executable and cannot become
   a tool argument or `self` memory without explicit approval.
4. Iris can read narrowly authorized calendar, task, document, and email
   sources, record provenance, and revoke each source without deleting the
   operator's original data.
5. Its salience engine runs in shadow mode, then sends only operator-approved,
   explainable, bounded proactive messages; a mute/stop command takes effect
   immediately.
6. Every consequential action requires the appropriate explicit approval;
   all inbound events, policy decisions, source reads, and actions have an
   append-only, privacy-preserving audit record.
7. The full automated suite passes without live accounts; each enabled live
   integration has a separate human acceptance gate.

## Non-goals

- Claims of consciousness, autonomous moral authority, or deceptive human
  impersonation.
- An unrestricted autonomous agent with access to all local files/accounts.
- Replacing Hera, Slack, Claude Code, Codex, Calendar, or email providers.
- Multi-tenant SaaS, public hosting, social-media automation, or growth loops.

## Context and constraints

- Iris already has a completed Hera trust-tier substrate in
  `/Users/randyren/Developer/second brain/hera`.
- `PLAN.md` is the active, narrow Slack Gateway + Agent Launcher plan. It is
  the first deliverable of this master plan and remains authoritative for that
  slice.
- Production stays local-first. External services are narrowly scoped and
  user-authorized; their raw content is treated as untrusted by default.
- Slack Socket Mode is the first conversational channel because it provides a
  separate bot identity without a public listener. iMessage is experimental,
  not a production dependency.
- Secrets reside in macOS Keychain, never source control, logs, prompts, or
  durable model memory.

## Assumptions and early risks

- A1: The operator will provide a private Slack workspace/app for the first
  live channel gate. → validate in CP-M0.
- A2: Hera's trust filtering remains correct as future memory writes and
  provenance features are added. → regression test at every phase.
- A3: Narrow, read-only integrations can provide enough utility before any
  write authority is introduced. → validate in CP-M3.
- A4: Proactive assistance is valuable only if relevance can be measured and
  the operator can mute it instantly. → shadow-mode evaluation in CP-M4.
- A5: A durable user model must distinguish observed facts, operator-stated
  facts, inferences, and revoked/corrected beliefs. → validate in CP-M2.

## Phase map

```text
M0 conversational gateway + coding orchestration
       │
       ├──► M1 provenance memory ─► M2 user model / corrections ─┐
       │                                                         ├──► M4 salience ─► M5 approved agency ─► FINAL
       └──► M3 permissioned read-only senses ───────────────────┘
```

M1 and M3 can proceed in parallel after M0. M2 depends on M1. M4 depends on
M2 and M3. M5 depends on M4.

---

## M0 — Conversational gateway and coding orchestration

**Goal:** A private Slack DM reaches an always-on Iris daemon whenever the
laptop is awake; Iris can hold a natural, safe conversation, orchestrate and
steer local coding sessions, and leave a complete audit trail.

**Depends on:** Hera trust-tier completion.

**Deliverables:** The completed narrow-gateway artifacts in `PLAN.md` through
`CP-FINAL`, plus S7's always-on runtime, conversational coordinator,
bidirectional coding-session transport, and live Jarvis acceptance result.

**M0 operational contract:** Iris is a local LaunchAgent, not a one-shot
terminal process. While the operator is logged in and the laptop is awake, it
maintains one outbound Socket Mode connection, reports a private atomic health
record, reconnects after sleep/network loss, and never starts duplicate event
consumers. "Listening" means connected and heartbeating, not merely that a PID
exists. The Straits harvester's launchd + bounded-state + single-flight +
staleness pattern is the reference implementation pattern.

**M0 interaction contract:** commands remain explicit safety controls, but a
plain allowed DM is a conversational turn. The agent can explain, ask a
clarifying question, summarize, and propose work. It cannot convert its own
text into a local action; typed capability policy and Slack approval remain the
sole path to consequential actions. Coding-agent progress, final responses,
and `@session` steering stay in the originating Slack thread.

```yaml
checkpoint:
  id: CP-M0
  phase: "always-on conversational Iris accepted"
  halt: true
  max_attempts: 2
  human_gate: true
  checks:
    - name: conversational-control-plane-passes
      run: ".venv/bin/python scripts/checkpoint_runner.py run CP-S7 --plan PLAN.md"
      expect: "exit 0"
    - name: launchd-online-contract
      run: ".venv/bin/python -m iris.irisctl verify-online"
      expect: "exit 0"
    - name: live-operator-conversation
      run: ".venv/bin/python -m iris.slack_probe --jarvis-acceptance"
      expect: "exit 0"
    - name: hera-trust-regression
      run: "cd '/Users/randyren/Developer/second brain/hera' && .venv/bin/python tests/test_inject_excludes_untrusted.py"
      expect: "exit 0"
```

---

## M1 — Provenance-first durable memory

**Goal:** Conversation outcomes and operator-approved facts become durable,
queryable Hera records with source, trust, lifecycle, and correction links.

**Depends on:** M0.

**Deliverables:** `iris/memory/`, Hera ingestion adapter, memory write policy,
provenance schema/migration, correction/revocation representation, and tests.

**Tasks:**
1. Define a typed memory record: claim, source reference, trust, authoring
   mode, confidence, created/updated time, lifecycle state, and supersedes
   reference.
2. Write only operator-confirmed or policy-approved records; preserve raw
   conversation data separately from distilled claims.
3. Implement retrieval with provenance labels and correction-aware ranking.
4. Add forget, correct, and inspect commands; forgetting hides a record from
   retrieval while retaining an auditable tombstone.

```yaml
checkpoint:
  id: CP-M1
  phase: "provenance memory"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: memory-record-roundtrip
      run: ".venv/bin/python -m pytest tests/test_memory_records.py tests/test_memory_provenance.py -q"
      expect: "exit 0"
    - name: correction-and-forget-hide-from-retrieval
      run: ".venv/bin/python -m pytest tests/test_memory_corrections.py tests/test_memory_forgetting.py -q"
      expect: "exit 0"
    - name: untrusted-content-cannot-cross-policy
      run: ".venv/bin/python -m pytest tests/test_memory_trust_boundary.py -q"
      expect: "exit 0"
    - name: hera-trust-regression
      run: "cd '/Users/randyren/Developer/second brain/hera' && .venv/bin/python tests/test_inject_excludes_untrusted.py"
      expect: "exit 0"
```

---

## M2 — User model and feedback loop

**Goal:** Iris can represent operator-stated preferences, observed patterns,
and tentative inferences without conflating them or becoming manipulative.

**Depends on:** M1.

**Deliverables:** `iris/user_model/`, explanation renderer, feedback commands,
preference confidence decay, and tests.

**Tasks:**
1. Separate stated facts, observations, and inferences in the schema.
2. Require explicit confirmation before a new high-impact preference becomes
   durable.
3. Let the operator inspect, correct, and delete every model entry.
4. Bound inference confidence and decay stale observations rather than turning
   them into permanent facts.

```yaml
checkpoint:
  id: CP-M2
  phase: "inspectable user model"
  halt: true
  max_attempts: 3
  human_gate: true
  checks:
    - name: stated-observed-inferred-separation
      run: ".venv/bin/python -m pytest tests/test_user_model_origins.py -q"
      expect: "exit 0"
    - name: correction-delete-and-explanation
      run: ".venv/bin/python -m pytest tests/test_user_model_controls.py tests/test_user_model_explanations.py -q"
      expect: "exit 0"
    - name: stale-inferences-decay
      run: ".venv/bin/python -m pytest tests/test_user_model_decay.py -q"
      expect: "exit 0"
```

---

## M3 — Permissioned, read-only senses

**Goal:** Iris can ingest narrow slices of Calendar, tasks, documents, and
email as revocable, provenance-tagged untrusted inputs.

**Depends on:** M0. Can run in parallel with M1/M2 where dependencies permit.

**Deliverables:** `iris/senses/`, per-source capability registry, Keychain
credential adapters, source revocation CLI, quarantine store, and fakes.

**Tasks:**
1. Ship one source at a time in read-only mode, beginning with Calendar.
2. Assign every source item `trust=untrusted` until an explicit promotion flow
   creates an attributed safe summary or operator-owned record.
3. Store only minimal metadata needed for salience; preserve source references
   and give the operator a revoke/purge command.
4. Add provider fakes so tests never need a live account.

```yaml
checkpoint:
  id: CP-M3
  phase: "revocable read-only senses"
  halt: true
  max_attempts: 3
  human_gate: true
  checks:
    - name: calendar-fake-ingestion
      run: ".venv/bin/python -m pytest tests/test_calendar_sense.py -q"
      expect: "exit 0"
    - name: source-policy-and-revocation
      run: ".venv/bin/python -m pytest tests/test_sense_capabilities.py tests/test_sense_revoke.py -q"
      expect: "exit 0"
    - name: raw-source-content-stays-quarantined
      run: ".venv/bin/python -m pytest tests/test_sense_quarantine.py -q"
      expect: "exit 0"
    - name: calendar-live-readonly-smoke
      run: ".venv/bin/python -m iris.senses.calendar_probe"
      expect: "exit 0"
```

---

## M4 — Explainable salience in shadow mode

**Goal:** Iris scores potentially helpful events without notifying the operator
until relevance and nuisance controls are observed and approved.

**Depends on:** M2, M3.

**Deliverables:** `iris/salience/`, score/explanation records, daily shadow
report, operator feedback labels, mute controls, and evaluation fixtures.

**Tasks:**
1. Implement deterministic, explainable features: deadline proximity,
   calendar conflict, project recency, explicit commitments, and user feedback.
2. Record candidate nudges in shadow mode; do not send proactive messages.
3. Require explicit promotion to notification mode and enforce per-day limits,
   quiet hours, source-specific mutes, and global `stop`.

```yaml
checkpoint:
  id: CP-M4
  phase: "salience shadow mode"
  halt: true
  max_attempts: 3
  human_gate: true
  checks:
    - name: score-has-explanation-and-provenance
      run: ".venv/bin/python -m pytest tests/test_salience_explanations.py -q"
      expect: "exit 0"
    - name: shadow-mode-never-notifies
      run: ".venv/bin/python -m pytest tests/test_salience_shadow_mode.py -q"
      expect: "exit 0"
    - name: mute-quiet-hours-and-budgets-hold
      run: ".venv/bin/python -m pytest tests/test_salience_controls.py -q"
      expect: "exit 0"
    - name: feedback-improves-ranked-fixture
      run: ".venv/bin/python -m pytest tests/test_salience_feedback.py -q"
      expect: "exit 0"
```

---

## M5 — Approved agency and self-improvement

**Goal:** Iris can turn an approved proposal into bounded action, learn from
outcomes, and draft reusable skills without granting itself new authority.

**Depends on:** M4.

**Deliverables:** capability policy table, approval UX, outcome ledger,
skill-draft directory, review workflow, and security tests.

**Tasks:**
1. Make every write/send/schedule action a typed capability with an explicit
   approval requirement and reversible outcome where possible.
2. Record outcomes and operator feedback; use them only to improve proposals,
   not silently expand permissions.
3. Allow Iris to draft skills into a non-loadable review directory; only a
   terminal-reviewed promotion makes a skill available to coding sessions.

```yaml
checkpoint:
  id: CP-M5
  phase: "bounded approved agency"
  halt: true
  max_attempts: 3
  human_gate: true
  checks:
    - name: consequential-actions-require-approval
      run: ".venv/bin/python -m pytest tests/test_capability_approvals.py -q"
      expect: "exit 0"
    - name: outcome-ledger-is-append-only
      run: ".venv/bin/python -m pytest tests/test_outcome_ledger.py -q"
      expect: "exit 0"
    - name: drafted-skills-cannot-autoload
      run: ".venv/bin/python -m pytest tests/test_skill_drafts.py -q"
      expect: "exit 0"
    - name: permission-scope-cannot-self-expand
      run: ".venv/bin/python -m pytest tests/test_no_self_escalation.py -q"
      expect: "exit 0"
```

---

## Final checkpoint

```yaml
checkpoint:
  id: CP-MASTER-FINAL
  phase: "trusted long-term collaborator acceptance"
  halt: true
  max_attempts: 2
  human_gate: true
  checks:
    - name: conversational-coding-orchestration
      run: ".venv/bin/python tests/acceptance/test_master_conversation.py"
      expect: "exit 0"
    - name: provenance-and-correction
      run: ".venv/bin/python tests/acceptance/test_master_memory.py"
      expect: "exit 0"
    - name: trust-boundary-holds
      run: ".venv/bin/python tests/acceptance/test_master_trust.py"
      expect: "exit 0"
    - name: senses-revocable-and-quarantined
      run: ".venv/bin/python tests/acceptance/test_master_senses.py"
      expect: "exit 0"
    - name: salience-is-explainable-and-mutable
      run: ".venv/bin/python tests/acceptance/test_master_salience.py"
      expect: "exit 0"
    - name: agency-cannot-bypass-approval
      run: ".venv/bin/python tests/acceptance/test_master_agency.py"
      expect: "exit 0"
    - name: full-suite-green
      run: ".venv/bin/python -m pytest -q"
      expect: "exit 0"
```

---

## Executor Protocol v1 (binding)

1. Execute phases in dependency order. Do not start a phase whose dependencies
   have not passed.
2. At each checkpoint, run every check exactly as written with
   `scripts/checkpoint_runner.py run <CP-ID>` and capture real output.
3. Report every check as PASS or FAIL with command evidence. Passing one narrow
   test does not prove a broader requirement.
4. On failure, fix the implementation and rerun the entire checkpoint.
5. After the configured maximum failed attempts, stop and present a Failure
   Report; do not continue to later phases.
6. Do not weaken or reinterpret a check. A scope or verifier change requires
   an explicit operator decision.
7. At a human gate, stop after automated checks and wait for explicit approval.
8. Completion requires CP-MASTER-FINAL to pass with current evidence.

### Checkpoint Report format

```text
## Checkpoint Report — CP-<n> (<phase>) — attempt <k>/<max>
- <check-name>: PASS|FAIL
  $ <command>
  <relevant real output>
Verdict: PASS → next phase | FAIL → next action
```

### Failure Report format

```text
## Failure Report — CP-<n> after <max> attempts
Failing checks + evidence: <...>
What was tried: <...>
Current hypothesis: <...>
Needed to unblock: <decision | access | scope change>
```
