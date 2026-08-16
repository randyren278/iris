# Plan: Iris — Projects 0 & 1 (Trust Tiers, Spikes, Gateway + Launcher)
Planned: 2026-08-17 · Executor protocol: v1 (embedded below, binding)

Design spec: `docs/superpowers/specs/2026-08-17-iris-personal-agent-design.md`

## Objective

Ship a launchd-managed daemon that lets the operator start and steer Claude Code and Codex sessions in any local project by text message from an allowlisted iPhone, with per-tool-call approval, while closing the memory-poisoning hole in the existing Hera vault before any untrusted content can reach it.

## Success criteria (re-verified by CP-FINAL)

1. Texting `cd <fuzzy-project-name>` then `claude <task>` from the allowlisted handle starts a Claude Code session in that directory and returns a reply within 30 s.
2. A tool call requiring approval texts the operator and blocks; `y` allows, `n` denies, and no reply within the timeout denies.
3. Texting `stop` terminates every running session and disarms the gateway.
4. Messages from non-allowlisted handles are ignored, never executed, and recorded in the audit log.
5. `prompt_inject.py` never injects a page whose `trust` is not `self` or `team`, proven by an automated test that plants an `untrusted` page and asserts absence.
6. Hera's existing e2e suite passes unchanged after the trust-tier migration.
7. The daemon starts on boot via launchd and appends every inbound message, decision, tool call, and approval to an append-only audit log.
8. The full gateway test suite passes without a phone attached, using the fake-`chat.db` harness.

## Non-goals

- Projects 2–5 from the spec (agent memory, senses, salience, voice). Each gets its own plan.
- The dual-LLM quarantine runtime. Only the **trust-tier substrate** it depends on ships here.
- Channels other than iMessage.
- Multi-user, SSO, admin console.
- Beating Poke on nudge quality — no proactive messaging in this plan at all.

## Context & constraints

**Environment:** macOS 26.5.2 (build 25F84), Apple Silicon · Python 3.13.13 at `/opt/homebrew/opt/python@3.13/libexec/bin/python3` · PyYAML 6.0.2 · sqlite 3.53.3 · `/usr/bin/osascript` · `/bin/launchctl`
**Repos:** Iris = `/Users/randyren/Developer/remote control` (git, initialized) · Hera = `/Users/randyren/Developer/second brain/hera` (git, has `.venv`)
**Tools:** Claude Code 2.1.220 (`--remote-control`, `--permission-mode manual`, `PreToolUse` hooks) · Codex 0.147.0 (`remote-control start|stop|pair`, `exec`)
**Access:** Full Disk Access grant required (manual, System Settings) · Automation permission for Messages (manual, first-run prompt)
**Deadline:** none stated.

## Assumptions

- **A1:** `~/Library/Messages/chat.db` becomes readable once Full Disk Access is granted to the Python interpreter. → validated at **CP-1.1**
- **A2:** AppleScript can send iMessages on macOS 26.5.2. Historically flaky across releases. → validated at **CP-1.2**
- **A3:** A Remote Control link/URL is obtainable from outside the session. **Believed false or undocumented.** → validated at **CP-1.3**; documented fallback is to text the session *name*.
- **A4:** The Mac can be kept awake and reachable. → validated at **CP-1.4**
- **A5:** `ALTER TABLE pages ADD COLUMN trust ...` is accepted by sqlite 3.53.3 with a non-null default. If the CHECK constraint is rejected, enforce in application code. → validated at **CP-2.1**
- **A6:** Hera's e2e suite currently passes on this machine. → validated at **CP-2.0** (baseline captured before any change)
- **A7:** Claude Code's `PreToolUse` hook can block on a network call long enough for a human to reply by text. → validated at **CP-5.2**
- **A8:** Codex's experimental `remote-control` interface is stable enough to wrap. Accepted risk — isolated behind an adapter, and CP-4.6 is the only checkpoint that depends on it.

## Phase map

```
P1 (spikes) ─────┐
                 ├──► P3 (skeleton) ──► P4 (grammar) ──► P5 (lanes+approvals) ──► P6 (fallback) ──► P7 (daemon) ──► CP-FINAL
P2 (trust tiers) ┘
```

**P1 and P2 are independent and may run in parallel.** P3 depends on both. Everything after P3 is strictly sequential.

---

# P1 — Spikes: kill the unknowns

**Goal:** Every assumption that could invalidate the transport is proven or disproven, with evidence written down, before any gateway code exists.
**Depends on:** —
**Deliverables:** `spikes/*.py`, `spikes/*.sh`, `SPIKE-RESULTS.md`

---

## P1.1 — chat.db readable

**Tasks:**
1. Grant Full Disk Access to `/opt/homebrew/opt/python@3.13/libexec/bin/python3` (System Settings → Privacy & Security → Full Disk Access). Note: the *interpreter binary* needs it, not the terminal alone.
2. Write `spikes/read_chatdb.py` — open `~/Library/Messages/chat.db` read-only via URI (`file:...?mode=ro`), count rows in `message`, print the 3 most recent `(ROWID, is_from_me, handle_id, text, date)`.
3. Record the result in `SPIKE-RESULTS.md`.

```yaml
checkpoint:
  id: CP-1.1
  phase: "Spike: chat.db readable"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: reads-chatdb-readonly
      run: "python3 spikes/read_chatdb.py"
      expect: "exit 0"
    - name: reports-nonzero-messages
      run: "python3 spikes/read_chatdb.py --count-only"
      expect: "exit 0"
    - name: does-not-write
      run: "python3 -c \"import pathlib,subprocess; p=pathlib.Path.home()/'Library/Messages/chat.db'; m=p.stat().st_mtime; subprocess.run(['python3','spikes/read_chatdb.py'],check=True,capture_output=True); assert p.stat().st_mtime==m, 'chat.db mtime changed'\""
      expect: "exit 0"
    - name: result-recorded
      run: "grep -q 'CP-1.1' SPIKE-RESULTS.md"
      expect: "exit 0"
```

---

## P1.2 — AppleScript can send

**Tasks:**
1. Write `spikes/send_imessage.sh <handle> <text>` wrapping `osascript`.
2. Send a test message to the operator's own handle (self-chat).
3. Confirm delivery by locating the sent row in `chat.db` with `is_from_me=1`.
4. Record outcome, including latency, in `SPIKE-RESULTS.md`.

```yaml
checkpoint:
  id: CP-1.2
  phase: "Spike: AppleScript send"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: send-exits-clean
      run: "bash spikes/send_imessage.sh \"$(cat .iris-test-handle)\" 'iris CP-1.2 probe'"
      expect: "exit 0"
    - name: message-lands-in-chatdb
      run: "python3 spikes/assert_sent.py 'iris CP-1.2 probe' --within-seconds 60"
      expect: "exit 0"
    - name: result-recorded
      run: "grep -q 'CP-1.2' SPIKE-RESULTS.md"
      expect: "exit 0"
```

---

## P1.3 — Remote Control link retrievability

**Tasks:**
1. Start `claude --remote-control iris-spike` in a scratch directory.
2. Attempt to obtain the link/session identity from outside the process: inspect `claude agents --json`, session files under `~/.claude/projects/`, process args, and any emitted state file.
3. Write `SPIKE-RESULTS.md` with a definitive **YES** (with the exact retrieval method) or **NO** (with the fallback: text the session name; operator selects it in the app).

**This checkpoint passes either way.** It exists to force a documented decision, not a particular answer.

```yaml
checkpoint:
  id: CP-1.3
  phase: "Spike: Remote Control link"
  halt: true
  max_attempts: 2
  human_gate: false
  checks:
    - name: agents-json-parses
      run: "claude agents --json | python3 -c 'import json,sys; json.load(sys.stdin)'"
      expect: "exit 0"
    - name: verdict-recorded
      run: "grep -Eq 'CP-1.3 verdict: (YES|NO)' SPIKE-RESULTS.md"
      expect: "exit 0"
    - name: fallback-documented-if-no
      run: "bash spikes/check_rc_verdict.sh"
      expect: "exit 0"
```

---

## P1.4 — Mac stays reachable

**Tasks:**
1. Decide the mechanism: `caffeinate -s` inside the launchd job vs. `pmset` changes. Record the choice and its battery cost.
2. Write `spikes/assert_awake.sh` asserting the chosen mechanism is in effect.

```yaml
checkpoint:
  id: CP-1.4
  phase: "Spike: stay awake"
  halt: true
  max_attempts: 2
  human_gate: false
  checks:
    - name: mechanism-chosen
      run: "grep -q 'CP-1.4 mechanism:' SPIKE-RESULTS.md"
      expect: "exit 0"
    - name: assertion-script-runs
      run: "bash spikes/assert_awake.sh"
      expect: "exit 0"
```

---

# P2 — Hera trust tiers

**Goal:** Hera pages carry a trust tier, and `prompt_inject.py` can no longer surface untrusted content into a privileged session. Ships before any sense exists.
**Depends on:** —
**Deliverables:** migration in Hera's `scripts/`, updated `search.py`, updated `.claude/hooks/prompt_inject.py`, new tests

> All P2 commands run inside the Hera repo. `$H` below denotes `/Users/randyren/Developer/second brain/hera`.

---

## P2.0 — Baseline

**Tasks:**
1. Run Hera's existing e2e suite and capture output to `baseline-hera-e2e.txt` in the Iris repo.
2. Record the current page count and schema hash.

```yaml
checkpoint:
  id: CP-2.0
  phase: "Hera baseline captured"
  halt: true
  max_attempts: 2
  human_gate: false
  checks:
    - name: doctor-passes
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python scripts/hera_db.py --doctor"
      expect: "exit 0"
    - name: baseline-file-exists
      run: "test -s baseline-hera-e2e.txt"
      expect: "exit 0"
    - name: page-count-recorded
      run: "grep -Eq 'pages: [0-9]+' baseline-hera-e2e.txt"
      expect: "exit 0"
```

---

## P2.1 — Schema migration

**Tasks:**
1. Add `trust TEXT NOT NULL DEFAULT 'self'` to `pages`, constrained to `self|team|untrusted` (CHECK if sqlite accepts it on ADD COLUMN; otherwise enforce in `_upsert_page`).
2. Make the migration idempotent — running it twice is a no-op.
3. Update `init_schema()` so fresh vaults get the column natively.

```yaml
checkpoint:
  id: CP-2.1
  phase: "trust column exists"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: column-present
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python -c \"import sys; sys.path.insert(0,'scripts'); import hera_db; c=hera_db.connect(); assert 'trust' in [r[1] for r in c.execute('PRAGMA table_info(pages)')], 'no trust column'\""
      expect: "exit 0"
    - name: migration-idempotent
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python scripts/migrate_trust.py && .venv/bin/python scripts/migrate_trust.py"
      expect: "exit 0"
    - name: invalid-tier-rejected
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python tests/test_trust_constraint.py"
      expect: "exit 0"
    - name: doctor-still-passes
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python scripts/hera_db.py --doctor"
      expect: "exit 0"
```

---

## P2.2 — Backfill existing pages

**Tasks:**
1. Set every pre-existing page to `trust='self'`.
2. Set every page indexed from `team.db` to `trust='team'` (or confirm team pages live only in `team.db` and need no backfill — record which).

```yaml
checkpoint:
  id: CP-2.2
  phase: "existing pages backfilled"
  halt: true
  max_attempts: 2
  human_gate: false
  checks:
    - name: no-null-trust
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python -c \"import sys; sys.path.insert(0,'scripts'); import hera_db; c=hera_db.connect(); n=c.execute(\\\"select count(*) from pages where trust is null or trust=''\\\").fetchone()[0]; assert n==0, f'{n} pages missing trust'\""
      expect: "exit 0"
    - name: page-count-unchanged
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python -c \"import sys,re,pathlib; sys.path.insert(0,'scripts'); import hera_db; c=hera_db.connect(); now=c.execute('select count(*) from pages').fetchone()[0]; base=int(re.search(r'pages: ([0-9]+)', pathlib.Path('/Users/randyren/Developer/remote control/baseline-hera-e2e.txt').read_text()).group(1)); assert now==base, 'page count changed'\""
      expect: "exit 0"
```

---

## P2.3 — Frontmatter emits trust

**Tasks:**
1. Extend `_frontmatter()` to emit `trust:` as an unquoted scalar (same treatment as `visibility`/`source_kind`/`owner`).
2. Make `ingest_source()` accept and persist a trust tier, defaulting to `self`.

```yaml
checkpoint:
  id: CP-2.3
  phase: "frontmatter carries trust"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: frontmatter-unit-test
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python tests/test_frontmatter_trust.py"
      expect: "exit 0"
    - name: emitted-unquoted
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python -c \"import sys; sys.path.insert(0,'scripts'); import ingest; print(ingest._frontmatter('01X','T','concept',extra={'trust':'untrusted'}))\" | grep -q '^trust: untrusted$'"
      expect: "exit 0"
```

---

## P2.4 — Search accepts a trust filter

**Tasks:**
1. Add a `trust_in` parameter to `hybrid_search()` (default `('self','team')`).
2. Apply the filter **before** RRF fusion so untrusted pages cannot consume ranking slots.
3. Same for `team_hybrid_search()`.

```yaml
checkpoint:
  id: CP-2.4
  phase: "hybrid_search filters by trust"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: filter-unit-test
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python tests/test_search_trust_filter.py"
      expect: "exit 0"
    - name: untrusted-never-returned-by-default
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python tests/test_search_default_excludes_untrusted.py"
      expect: "exit 0"
    - name: explicit-opt-in-still-works
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python tests/test_search_explicit_untrusted.py"
      expect: "exit 0"
```

---

## P2.5 — Inject hook filters untrusted

**Tasks:**
1. Update `.claude/hooks/prompt_inject.py` to pass the default `trust_in` filter.
2. Delimit `team`-tier pointers with explicit attribution in the injected text.
3. Preserve the fail-open contract: any error → no output, exit 0.

```yaml
checkpoint:
  id: CP-2.5
  phase: "inject hook is trust-aware"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: planted-untrusted-page-not-injected
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python tests/test_inject_excludes_untrusted.py"
      expect: "exit 0"
    - name: self-pages-still-injected
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python tests/test_inject_includes_self.py"
      expect: "exit 0"
    - name: team-pages-attributed
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python tests/test_inject_team_attribution.py"
      expect: "exit 0"
    - name: fails-open-on-error
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && echo 'not json' | .venv/bin/python .claude/hooks/prompt_inject.py"
      expect: "exit 0"
```

---

## P2.6 — Hera regression

**Tasks:**
1. Run the full existing e2e suite.
2. Diff against `baseline-hera-e2e.txt`; investigate every difference.

```yaml
checkpoint:
  id: CP-2.6
  phase: "Hera regression clean"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: e2e-suite-passes
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && bash scripts/e2e_final.sh"
      expect: "exit 0"
    - name: inject-e2e-passes
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && bash scripts/e2e_inject.sh"
      expect: "exit 0"
    - name: team-isolation-passes
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && bash scripts/e2e_team_isolation.sh"
      expect: "exit 0"
    - name: doctor-passes
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python scripts/hera_db.py --doctor"
      expect: "exit 0"
```

---

# P3 — Walking skeleton: text in, text out

**Goal:** A running daemon that receives a text from the allowlisted handle and echoes it back — the full I/O loop, no intelligence. Plus the fake-`chat.db` harness that makes every later phase testable without a phone.
**Depends on:** P1, P2

---

## P3.1 — Scaffold and fake-chat.db harness

**Tasks:**
1. Create `iris/` package, `tests/`, `pyproject.toml`, pinned deps.
2. Build `tests/fakedb.py`: creates a temp SQLite file with Apple's `message`/`handle`/`chat` schema shape, and `inject(handle, text)` to append a row as if received.
3. Build `tests/fakesend.py`: a recording stub replacing the AppleScript sender.
4. Make the daemon's chat.db path and sender injectable via config.

**This is the highest-leverage task in the plan.** Everything downstream is verifiable because of it.

```yaml
checkpoint:
  id: CP-3.1
  phase: "scaffold + fake harness"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: package-imports
      run: "python3 -c 'import iris; print(iris.__version__)'"
      expect: "exit 0"
    - name: fakedb-roundtrip
      run: "python3 -m pytest tests/test_fakedb.py -q"
      expect: "exit 0"
    - name: fakedb-schema-matches-real
      run: "python3 tests/assert_schema_parity.py"
      expect: "exit 0"
    - name: test-suite-runs
      run: "python3 -m pytest -q"
      expect: "exit 0"
```

---

## P3.2 — Poller

**Tasks:**
1. `iris/poller.py`: read-only URI open, poll every 2 s, track high-water `ROWID`, yield new inbound rows only (`is_from_me=0`).
2. Persist the high-water mark so a restart does not replay history.

```yaml
checkpoint:
  id: CP-3.2
  phase: "poller yields new messages only"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: yields-injected-message
      run: "python3 -m pytest tests/test_poller.py -q"
      expect: "exit 0"
    - name: no-replay-after-restart
      run: "python3 -m pytest tests/test_poller_highwater.py -q"
      expect: "exit 0"
    - name: ignores-outbound
      run: "python3 -m pytest tests/test_poller_ignores_from_me.py -q"
      expect: "exit 0"
    - name: opens-readonly
      run: "grep -q 'mode=ro' iris/poller.py"
      expect: "exit 0"
```

---

## P3.3 — Allowlist

**Tasks:**
1. `iris/allowlist.py`: exact-match handle comparison, loaded from `~/.iris/config.toml`.
2. **Mutation is terminal-only.** No inbound message path may alter the allowlist.
3. Non-allowlisted messages are dropped and logged.

```yaml
checkpoint:
  id: CP-3.3
  phase: "allowlist enforced"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: allowed-handle-passes
      run: "python3 -m pytest tests/test_allowlist_allow.py -q"
      expect: "exit 0"
    - name: unknown-handle-dropped
      run: "python3 -m pytest tests/test_allowlist_deny.py -q"
      expect: "exit 0"
    - name: no-substring-or-prefix-match
      run: "python3 -m pytest tests/test_allowlist_exact.py -q"
      expect: "exit 0"
    - name: message-cannot-mutate-allowlist
      run: "python3 -m pytest tests/test_allowlist_immutable_from_message.py -q"
      expect: "exit 0"
```

---

## P3.4 — Sender

**Tasks:**
1. `iris/sender.py`: AppleScript send with shell-safe argument passing (no string interpolation into the script body).
2. Retry with backoff on transient failure; never retry forever.

```yaml
checkpoint:
  id: CP-3.4
  phase: "sender works and is injection-safe"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: sender-unit-tests
      run: "python3 -m pytest tests/test_sender.py -q"
      expect: "exit 0"
    - name: applescript-quoting-safe
      run: "python3 -m pytest tests/test_sender_quoting.py -q"
      expect: "exit 0"
    - name: retry-bounded
      run: "python3 -m pytest tests/test_sender_retry.py -q"
      expect: "exit 0"
```

---

## P3.5 — Echo loop end-to-end

**Tasks:**
1. Wire poller → allowlist → echo → sender.
2. `iris/main.py` runs the loop against config-supplied paths.

```yaml
checkpoint:
  id: CP-3.5
  phase: "WALKING SKELETON: echo loop"
  halt: true
  max_attempts: 3
  human_gate: true
  checks:
    - name: echo-roundtrip-fake
      run: "python3 -m pytest tests/test_echo_e2e.py -q"
      expect: "exit 0"
    - name: unknown-sender-no-echo
      run: "python3 -m pytest tests/test_echo_rejects_unknown.py -q"
      expect: "exit 0"
    - name: full-suite-green
      run: "python3 -m pytest -q"
      expect: "exit 0"
```

> `human_gate: true` — send a real text from the real phone once here. This is the only place in P3 a phone is required, and it validates the fake harness against reality.

---

# P4 — Grammar, projects, sessions

**Goal:** Texts become commands; commands start real agent sessions.
**Depends on:** P3

---

## P4.1 — Grammar parser (pure)

**Tasks:**
1. `iris/grammar.py`: pure function `parse(text) -> Command | Unparsed`. No I/O, no side effects.
2. Cover: `ls`, `projects`, `cd <x>`, `claude <p>`, `codex <p>`, `sessions`, `@<n> <p>`, `link`, `y`, `n`, `kill <n>`, `stop`.

```yaml
checkpoint:
  id: CP-4.1
  phase: "grammar parses"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: every-command-parses
      run: "python3 -m pytest tests/test_grammar.py -q"
      expect: "exit 0"
    - name: unknown-returns-unparsed
      run: "python3 -m pytest tests/test_grammar_unparsed.py -q"
      expect: "exit 0"
    - name: parser-is-pure
      run: "python3 -m pytest tests/test_grammar_purity.py -q"
      expect: "exit 0"
    - name: case-and-whitespace-tolerant
      run: "python3 -m pytest tests/test_grammar_tolerance.py -q"
      expect: "exit 0"
```

---

## P4.2 — Project discovery

**Tasks:**
1. `iris/projects.py`: enumerate directories under configured roots (default `~/Developer`), skipping dotfiles and non-directories.
2. Cap and paginate output so a reply fits a text message.

```yaml
checkpoint:
  id: CP-4.2
  phase: "ls lists projects"
  halt: true
  max_attempts: 2
  human_gate: false
  checks:
    - name: lists-projects
      run: "python3 -m pytest tests/test_projects_list.py -q"
      expect: "exit 0"
    - name: output-fits-message-budget
      run: "python3 -m pytest tests/test_projects_pagination.py -q"
      expect: "exit 0"
```

---

## P4.3 — cd with fuzzy match

**Tasks:**
1. Fuzzy-match the argument against project names.
2. **Ambiguity must not guess** — reply with the candidate list instead.
3. Handle directory names containing spaces (the Iris repo itself is `remote control`).

```yaml
checkpoint:
  id: CP-4.3
  phase: "cd resolves projects"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: exact-and-fuzzy-match
      run: "python3 -m pytest tests/test_cd_match.py -q"
      expect: "exit 0"
    - name: ambiguous-lists-candidates
      run: "python3 -m pytest tests/test_cd_ambiguous.py -q"
      expect: "exit 0"
    - name: handles-spaces-in-path
      run: "python3 -m pytest tests/test_cd_spaces.py -q"
      expect: "exit 0"
    - name: rejects-traversal
      run: "python3 -m pytest tests/test_cd_no_traversal.py -q"
      expect: "exit 0"
```

---

## P4.4 — Session registry

**Tasks:**
1. `iris/registry.py` persisting `~/.iris/sessions.json`: `id`, `tool`, `cwd`, `session_id`, `remote_control_name`, `lane`, `state`, `last_activity`, `trust_policy`.
2. Atomic writes; survives restart; reaps dead processes on load.

```yaml
checkpoint:
  id: CP-4.4
  phase: "session registry persists"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: crud-roundtrip
      run: "python3 -m pytest tests/test_registry.py -q"
      expect: "exit 0"
    - name: survives-restart
      run: "python3 -m pytest tests/test_registry_persistence.py -q"
      expect: "exit 0"
    - name: atomic-write-no-corruption
      run: "python3 -m pytest tests/test_registry_atomic.py -q"
      expect: "exit 0"
    - name: reaps-dead-sessions
      run: "python3 -m pytest tests/test_registry_reap.py -q"
      expect: "exit 0"
```

---

## P4.5 — Launch Claude Code

**Tasks:**
1. `iris/launchers/claude.py`: spawn in the active project directory, register the session, return an identity per the CP-1.3 verdict (link if YES, session name if NO).
2. Pass `--permission-mode manual` and the `PreToolUse` hook config.

```yaml
checkpoint:
  id: CP-4.5
  phase: "claude sessions launch"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: launches-in-correct-cwd
      run: "python3 -m pytest tests/test_launch_claude_cwd.py -q"
      expect: "exit 0"
    - name: registers-session
      run: "python3 -m pytest tests/test_launch_claude_registry.py -q"
      expect: "exit 0"
    - name: passes-manual-permission-mode
      run: "python3 -m pytest tests/test_launch_claude_flags.py -q"
      expect: "exit 0"
    - name: real-launch-smoke
      run: "bash tests/smoke_launch_claude.sh"
      expect: "exit 0"
```

---

## P4.6 — Launch Codex

**Tasks:**
1. `iris/launchers/codex.py` behind the same adapter interface as Claude.
2. Isolate every Codex-specific assumption here (A8).

```yaml
checkpoint:
  id: CP-4.6
  phase: "codex sessions launch"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: adapter-interface-parity
      run: "python3 -m pytest tests/test_launcher_interface.py -q"
      expect: "exit 0"
    - name: launches-in-correct-cwd
      run: "python3 -m pytest tests/test_launch_codex_cwd.py -q"
      expect: "exit 0"
    - name: real-launch-smoke
      run: "bash tests/smoke_launch_codex.sh"
      expect: "exit 0"
```

---

## P4.7 — sessions / kill / stop

**Tasks:**
1. `sessions` renders the registry compactly.
2. `kill <n>` terminates one session and updates state.
3. `stop` terminates **all** sessions and disarms the gateway until re-armed from the terminal.

```yaml
checkpoint:
  id: CP-4.7
  phase: "session control commands"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: sessions-renders
      run: "python3 -m pytest tests/test_cmd_sessions.py -q"
      expect: "exit 0"
    - name: kill-terminates-one
      run: "python3 -m pytest tests/test_cmd_kill.py -q"
      expect: "exit 0"
    - name: stop-kills-all-and-disarms
      run: "python3 -m pytest tests/test_cmd_stop.py -q"
      expect: "exit 0"
    - name: disarmed-gateway-ignores-commands
      run: "python3 -m pytest tests/test_disarmed.py -q"
      expect: "exit 0"
```

---

# P5 — Lanes and approvals

**Goal:** Concurrent messages cannot corrupt a transcript, and no risky tool call runs without the operator's reply.
**Depends on:** P4

---

## P5.1 — Serialized session lanes

**Tasks:**
1. One in-flight turn per lane; queue the rest (OpenClaw's pattern).
2. Distinct sessions run concurrently; the same session serializes.

```yaml
checkpoint:
  id: CP-5.1
  phase: "lanes serialize"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: same-lane-serializes
      run: "python3 -m pytest tests/test_lane_serial.py -q"
      expect: "exit 0"
    - name: different-lanes-parallel
      run: "python3 -m pytest tests/test_lane_parallel.py -q"
      expect: "exit 0"
    - name: burst-preserves-order
      run: "python3 -m pytest tests/test_lane_burst_order.py -q"
      expect: "exit 0"
```

---

## P5.2 — PreToolUse hook

**Tasks:**
1. `hooks/iris_approve.py`: POSTs the pending tool call to the daemon and blocks on the verdict.
2. Validate A7 — that the hook can block long enough for a human reply.
3. Fail **closed**: daemon unreachable → deny.

```yaml
checkpoint:
  id: CP-5.2
  phase: "approval hook blocks"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: hook-blocks-until-verdict
      run: "python3 -m pytest tests/test_hook_blocks.py -q"
      expect: "exit 0"
    - name: fails-closed-when-daemon-down
      run: "python3 -m pytest tests/test_hook_fail_closed.py -q"
      expect: "exit 0"
    - name: long-block-tolerated
      run: "python3 -m pytest tests/test_hook_long_block.py -q"
      expect: "exit 0"
```

---

## P5.3 — Approval queue and y/n

**Tasks:**
1. Queue pending approvals; text the operator a readable rendering of the tool call.
2. `y`/`n` resolve the **oldest** pending approval; `y2`/`n2` address a specific one.

```yaml
checkpoint:
  id: CP-5.3
  phase: "y/n resolves approvals"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: y-allows
      run: "python3 -m pytest tests/test_approval_yes.py -q"
      expect: "exit 0"
    - name: n-denies
      run: "python3 -m pytest tests/test_approval_no.py -q"
      expect: "exit 0"
    - name: indexed-approval-targets-correct-item
      run: "python3 -m pytest tests/test_approval_indexed.py -q"
      expect: "exit 0"
    - name: rendering-is-readable
      run: "python3 -m pytest tests/test_approval_rendering.py -q"
      expect: "exit 0"
```

---

## P5.4 — Timeout denies

**Tasks:**
1. Configurable timeout; on expiry, deny and notify.

```yaml
checkpoint:
  id: CP-5.4
  phase: "timeout denies"
  halt: true
  max_attempts: 2
  human_gate: false
  checks:
    - name: timeout-denies
      run: "python3 -m pytest tests/test_approval_timeout.py -q"
      expect: "exit 0"
    - name: operator-notified-on-timeout
      run: "python3 -m pytest tests/test_approval_timeout_notify.py -q"
      expect: "exit 0"
```

---

# P6 — Output policy and LLM fallback

**Goal:** Replies stay readable, and unrecognized input becomes a *proposal*, never an action.
**Depends on:** P5

---

## P6.1 — Output policy

**Tasks:**
1. Under threshold → inline. Over → summarize and attach the session identity.
2. Never split mid-word; never send more than N messages per turn.

```yaml
checkpoint:
  id: CP-6.1
  phase: "output policy"
  halt: true
  max_attempts: 2
  human_gate: false
  checks:
    - name: short-inline
      run: "python3 -m pytest tests/test_output_short.py -q"
      expect: "exit 0"
    - name: long-summarized
      run: "python3 -m pytest tests/test_output_long.py -q"
      expect: "exit 0"
    - name: message-count-bounded
      run: "python3 -m pytest tests/test_output_burst_cap.py -q"
      expect: "exit 0"
```

---

## P6.2 — LLM fallback translator

**Tasks:**
1. Unparsed input → `claude -p --json-schema` on a cheap model, grammar in the prompt, returns a **proposed** command.
2. **The translator has no tools and never executes.** Structurally, not by instruction.
3. Off-schema output fails closed to "I didn't understand that."

```yaml
checkpoint:
  id: CP-6.2
  phase: "fallback proposes only"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: translates-natural-language
      run: "python3 -m pytest tests/test_fallback_translate.py -q"
      expect: "exit 0"
    - name: translator-has-no-tools
      run: "python3 -m pytest tests/test_fallback_no_tools.py -q"
      expect: "exit 0"
    - name: off-schema-fails-closed
      run: "python3 -m pytest tests/test_fallback_off_schema.py -q"
      expect: "exit 0"
    - name: never-executes-directly
      run: "python3 -m pytest tests/test_fallback_never_executes.py -q"
      expect: "exit 0"
```

---

## P6.3 — Confirm before execute

**Tasks:**
1. Proposals are texted as `did you mean: <cmd>? [y/n]` and require confirmation.
2. Confirmations expire.

```yaml
checkpoint:
  id: CP-6.3
  phase: "proposals require confirmation"
  halt: true
  max_attempts: 2
  human_gate: false
  checks:
    - name: proposal-requires-yes
      run: "python3 -m pytest tests/test_proposal_confirm.py -q"
      expect: "exit 0"
    - name: proposal-expires
      run: "python3 -m pytest tests/test_proposal_expiry.py -q"
      expect: "exit 0"
```

---

# P7 — Daemonize and harden

**Goal:** It runs on boot, logs everything, and can be audited.
**Depends on:** P6

---

## P7.1 — launchd

**Tasks:**
1. `~/Library/LaunchAgents/com.iris.gateway.plist` with `KeepAlive` and the CP-1.4 wake mechanism.
2. `scripts/install.sh` / `scripts/uninstall.sh`, both idempotent.

```yaml
checkpoint:
  id: CP-7.1
  phase: "runs under launchd"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: install-idempotent
      run: "bash scripts/install.sh && bash scripts/install.sh"
      expect: "exit 0"
    - name: job-loaded
      run: "launchctl list | grep -q com.iris.gateway"
      expect: "exit 0"
    - name: survives-kill
      run: "bash tests/test_keepalive.sh"
      expect: "exit 0"
    - name: uninstall-clean
      run: "bash scripts/uninstall.sh && ! launchctl list | grep -q com.iris.gateway"
      expect: "exit 0"
```

---

## P7.2 — Audit log

**Tasks:**
1. Append-only JSONL at `~/.iris/audit.jsonl`: every inbound message, parse verdict, launch, tool call, approval, denial, and error.
2. Rotation without losing history. Never log secrets or message bodies from non-allowlisted senders beyond a hash.

```yaml
checkpoint:
  id: CP-7.2
  phase: "audit log complete"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: every-event-type-logged
      run: "python3 -m pytest tests/test_audit_coverage.py -q"
      expect: "exit 0"
    - name: append-only
      run: "python3 -m pytest tests/test_audit_append_only.py -q"
      expect: "exit 0"
    - name: rotation-preserves-history
      run: "python3 -m pytest tests/test_audit_rotation.py -q"
      expect: "exit 0"
    - name: no-secrets-logged
      run: "python3 -m pytest tests/test_audit_no_secrets.py -q"
      expect: "exit 0"
```

---

## P7.3 — Security audit command

**Tasks:**
1. `iris doctor` — checks Full Disk Access, allowlist non-empty, state dir mode `700`, daemon bound to nothing network-facing, launchd loaded.
2. Non-zero exit on any misconfiguration (OpenClaw's `security audit` pattern).

```yaml
checkpoint:
  id: CP-7.3
  phase: "iris doctor"
  halt: true
  max_attempts: 3
  human_gate: false
  checks:
    - name: doctor-passes-clean-install
      run: "python3 -m iris.doctor"
      expect: "exit 0"
    - name: doctor-fails-on-bad-perms
      run: "python3 -m pytest tests/test_doctor_detects_bad_perms.py -q"
      expect: "exit 0"
    - name: doctor-fails-on-empty-allowlist
      run: "python3 -m pytest tests/test_doctor_empty_allowlist.py -q"
      expect: "exit 0"
    - name: state-dir-is-700
      run: "test \"$(stat -f '%Lp' ~/.iris)\" = '700'"
      expect: "exit 0"
```

---

## P7.4 — No network listener

**Tasks:**
1. Confirm the approval endpoint binds loopback only, or uses a unix socket.
2. Assert no non-loopback listener exists.

```yaml
checkpoint:
  id: CP-7.4
  phase: "no external attack surface"
  halt: true
  max_attempts: 2
  human_gate: false
  checks:
    - name: no-non-loopback-listener
      run: "bash tests/assert_loopback_only.sh"
      expect: "exit 0"
    - name: unix-socket-or-loopback-documented
      run: "grep -Eq '(AF_UNIX|127\\.0\\.0\\.1|localhost)' iris/approval_server.py"
      expect: "exit 0"
```

---

# Final checkpoint

```yaml
checkpoint:
  id: CP-FINAL
  phase: "End-to-end acceptance"
  halt: true
  max_attempts: 2
  human_gate: true
  checks:
    - name: sc1-launch-from-phone
      run: "python3 -m pytest tests/acceptance/test_sc1_launch.py -q"
      expect: "exit 0"
    - name: sc2-approval-flow
      run: "python3 -m pytest tests/acceptance/test_sc2_approval.py -q"
      expect: "exit 0"
    - name: sc3-stop-kills-everything
      run: "python3 -m pytest tests/acceptance/test_sc3_stop.py -q"
      expect: "exit 0"
    - name: sc4-unknown-sender-ignored
      run: "python3 -m pytest tests/acceptance/test_sc4_allowlist.py -q"
      expect: "exit 0"
    - name: sc5-untrusted-never-injected
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && .venv/bin/python tests/test_inject_excludes_untrusted.py"
      expect: "exit 0"
    - name: sc6-hera-regression-clean
      run: "cd \"/Users/randyren/Developer/second brain/hera\" && bash scripts/e2e_final.sh"
      expect: "exit 0"
    - name: sc7-launchd-and-audit
      run: "launchctl list | grep -q com.iris.gateway && test -s ~/.iris/audit.jsonl"
      expect: "exit 0"
    - name: sc8-suite-green-without-phone
      run: "python3 -m pytest -q"
      expect: "exit 0"
    - name: doctor-clean
      run: "python3 -m iris.doctor"
      expect: "exit 0"
```

> `human_gate: true` — the operator sends real texts from the real phone and confirms the loop works in the physical world, not just against the fake harness.

---

## Executor Protocol v1 (binding)

1. Execute phases in dependency order. Never start a phase whose dependencies' checkpoints have not PASSED.
2. At every `checkpoint` with `halt: true`: STOP. Run every check exactly as written — when `scripts/checkpoint_runner.py` is present, use `python scripts/checkpoint_runner.py run <CP-ID>`, which executes the checks and prints the report. Capture the real output.
3. Emit a Checkpoint Report (format below) with per-check PASS/FAIL and pasted evidence. A claim of "done" without pasted output is not done.
4. All checks pass → mark the phase complete and proceed. Any check fails → diagnose, fix the *work*, then re-run ALL checks in the checkpoint, not just the failed one.
5. After `max_attempts` failed attempts: halt the entire run. Emit a Failure Report (format below) and escalate. Do not continue to later phases.
6. Never edit, weaken, skip, or reinterpret a check to make it pass. If you believe a check itself is wrong, halt and say so explicitly in a Failure Report — changing the verifier is a human decision, not an executor decision.
7. `human_gate: true` → even on all-pass, stop and wait for explicit human approval before proceeding.
8. The project is complete only when CP-FINAL passes. CP-FINAL re-verifies the Success criteria from a clean state.

### Checkpoint Report format
```
## Checkpoint Report — CP-<n> (<phase>) — attempt <k>/<max>
- <check-name>: PASS|FAIL
  $ <command>
  <first/last relevant lines of real output>
Verdict: PASS → proceeding to <next phase> | FAIL → <next action>
```

### Failure Report format
```
## Failure Report — CP-<n> after <max> attempts
Failing checks + evidence: <...>
What was tried: <...>
Current hypothesis: <...>
Needed to unblock: <decision | access | fix to check | scope change>
```
