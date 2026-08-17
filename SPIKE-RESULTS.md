# Spike results — P1

Executed 2026-08-17 on macOS 26.5.2 (build 25F84), Apple Silicon.
Python 3.13.13 at `/opt/homebrew/opt/python@3.13/libexec/bin/python3` (= `python3` on PATH).
Claude Code 2.1.220.

Order of execution was forced by an external blocker: **Full Disk Access is not
granted**, so CP-1.3 and CP-1.4 ran first and CP-1.1 / CP-1.2 are blocked.

| Checkpoint | Assumption | Outcome |
|---|---|---|
| CP-1.1 chat.db readable | A1 | **BLOCKED** — Full Disk Access not granted |
| CP-1.2 AppleScript send | A2 | **SENDING PROVEN** (see Orchestrator Correction below) — still blocked only on FDA for the `chat.db` receipt assertion |
| CP-1.3 Remote Control link | A3 | **PASS — assumption A3 is TRUE** (plan expected false) |
| CP-1.4 Mac stays reachable | A4 | **PASS** |

---

## CP-1.3 — Remote Control link retrievability

### CP-1.3 verdict: YES

A Remote Control link **is** obtainable from outside the session. This
contradicts assumption A3 in PLAN.md ("Believed false or undocumented"), and it
simplifies P4.5: `claude <task>` can text back a tappable link, not a name the
operator has to hunt for in the app.

### Where the link lives

Claude Code writes one file per live session at `~/.claude/sessions/<pid>.json`.
When the session was started with `--remote-control`, that file gains a
**`bridgeSessionId`** field a few seconds after launch, once the bridge
connects. The shareable link is:

```
https://claude.ai/code/<bridgeSessionId>
```

Observed file for the spike session (pid 93962):

```json
{
    "pid": 93962,
    "sessionId": "dc267ab0-5c77-49bf-b72b-ed14465bc18c",
    "cwd": "/private/tmp/iris-spike",
    "startedAt": 1786921715181,
    "procStart": "Sun Aug 16 23:08:34 2026",
    "version": "2.1.220",
    "peerProtocol": 1,
    "kind": "interactive",
    "entrypoint": "cli",
    "name": "iris-spike-50",
    "nameSource": "derived",
    "status": "idle",
    "updatedAt": 1786921715269,
    "statusUpdatedAt": 1786921715269,
    "bridgeSessionId": "session_01CRhY1NHuGZXrR9NohQccCL"
}
```

### Working retrieval command

```
$ python3 spikes/rc_link.py 93962 --timeout 10
https://claude.ai/code/session_01CRhY1NHuGZXrR9NohQccCL
```

Or without the helper:

```
python3 -c "import json,pathlib; d=json.loads(pathlib.Path.home().joinpath('.claude/sessions/93962.json').read_text()); print('https://claude.ai/code/'+d['bridgeSessionId'])"
```

`spikes/rc_link.py` polls, because the bridge connects a few seconds after
launch and the field is absent until then.

### Corroboration

The session's own status line printed the identical URL:

```
/remote-control is active · Continue here, on your phone, or at
https://claude.ai/code/session_01CRhY1NHuGZXrR9NohQccCL
```

Retrieved out-of-process and printed in-process agree exactly. That is the
proof: the daemon never has to scrape a terminal.

### What does NOT work

- **`claude agents --json` does not carry the link.** It parses fine and lists
  every live session, but the record stops at `pid / cwd / kind / startedAt /
  sessionId / name / status`. No `bridgeSessionId`:
  ```json
  {"pid": 93962, "cwd": "/private/tmp/iris-spike", "kind": "interactive",
   "startedAt": 1786921715181, "sessionId": "dc267ab0-5c77-49bf-b72b-ed14465bc18c",
   "name": "iris-spike-50", "status": "idle"}
  ```
- **Process args do not carry it.** `ps` shows only
  `claude --remote-control iris-spike-rc`.
- **`~/.claude/projects/<slug>/<uuid>.jsonl`** (the transcript) mentions
  `session_01…` ids but is large and append-only; the sessions file is the
  cheap, authoritative source.
- **`~/.claude/daemon/roster.json`** is the *background-agent* supervisor's
  state (`claude --bg`), unrelated to Remote Control. Do not confuse the two.
- There is no `claude remote-control` subcommand (Codex has one; Claude Code
  exposes only the `--remote-control [name]` flag and
  `--remote-control-session-name-prefix`).

### Gotchas that cost real time here — carry them into P4.5

1. **`CLAUDE_CODE_CHILD_SESSION` suppresses registration entirely.** When
   `--remote-control` is launched from inside another Claude Code session, the
   child inherits that marker, prints
   `⚠ Transcript saving is off — inherited CLAUDE_CODE_CHILD_SESSION marker`,
   and **never writes `~/.claude/sessions/<pid>.json` at all** — it is also
   absent from `claude agents --json`. The launcher must scrub `CLAUDE*` from
   the child environment. Under launchd this is naturally clean, but any
   agent-driven test harness must do it explicitly.
2. **A first-run workspace-trust prompt blocks startup** in any directory the
   user has not previously trusted (`Yes, I trust this folder`). A daemon
   spawning sessions in arbitrary project directories will hang on this. P4.5
   must either pre-seed trust or detect and surface the prompt.
3. **The `<name>` argument is not the local display name.** Passing
   `--remote-control iris-spike-rc` produced `"name": "iris-spike-50"` with
   `"nameSource": "derived"` — derived from the cwd, exactly like the
   non-RC sessions (`remote-control-e9`, `hera-30`). The string `iris-spike-rc`
   appears nowhere in `~/.claude`. Do not key the registry on the name you
   passed; key it on pid, and read `bridgeSessionId` from the sessions file.
4. `--remote-control` is interactive-only; it needs a pty. `spikes/rc_link.py`
   only reads state, so the daemon does not need to parse terminal output.

### CP-1.3 fallback: (retained as contingency, not needed)

If a future Claude Code release drops `bridgeSessionId` from
`~/.claude/sessions/<pid>.json`, fall back to texting the operator the session
**name** (`claude agents --json` → `.name`, e.g. `remote-control-e9`) and having
them select it in the Claude app. Cost of that fallback: one extra manual
selection step per session, ambiguity when two sessions share a cwd-derived
name prefix, and no way to deep-link from the text message — which is why the
YES path is worth depending on.

### Verifier

`spikes/check_rc_verdict.sh` — exits 0 if a `CP-1.3 verdict: YES|NO` line
exists, and additionally requires a `CP-1.3 fallback:` section when the verdict
is NO.

### Cleanup

The scratch session (`/private/tmp/iris-spike`) was killed, and
`/tmp/iris-spike` plus `~/.claude/projects/-private-tmp-iris-spike` removed.
`claude agents --json` is back to its pre-spike set. One residue was
deliberately left alone: the workspace-trust entry for `/private/tmp/iris-spike`
in `~/.claude.json`, because hand-editing that file is riskier than a stale
entry for a directory that no longer exists.

---

## CP-1.4 — Mac stays reachable

### CP-1.4 mechanism: `/usr/bin/caffeinate -i -s` wrapping the daemon inside the launchd job — no permanent `pmset` change

The launchd job's `ProgramArguments` become
`/usr/bin/caffeinate -i -s <python> -m iris.main`, so the power assertions are
created on the daemon's behalf and are released the instant it exits. Nothing
about the machine's configured power behaviour is modified, and there is no
cleanup step that can be missed.

**Why not `pmset`.** Changing `sleep`/`standby` is global, survives reboot,
outlives the daemon, and silently changes the machine's behaviour when Iris is
not running. `caffeinate` is scoped to the daemon's lifetime, which is the
correct blast radius.

**Why `-i -s` and not `-s` alone.** `caffeinate -s` is documented as *"valid
only when system is running on AC power"*. This machine is currently on battery
(`pmset -g ps` → `Now drawing from 'Battery Power'`), so `-s` alone would be a
no-op exactly when reachability matters most. `-i` (prevent idle system sleep)
applies on either power source. Both assertions were observed:

```
   pid 95649(caffeinate): PreventUserIdleSystemSleep named: "caffeinate command-line tool"
   pid 95649(caffeinate): PreventSystemSleep named: "caffeinate command-line tool"
```

**No user power settings were changed by this spike.** `pmset -g custom` still
reads `sleep 1` / `standby 1` on both battery and AC, exactly as before.

### Battery cost

Measured on this machine while the spike ran:

- Draw: `InstantAmperage = -730 mA` at `Voltage = 12237 mV` → **8.93 W**, stable
  across three samples. This is a *loaded* figure — several Claude Code agents
  and Safari media playback were running — not the idle cost of the gateway.
- Battery: `AppleRawMaxCapacity = 5102 mAh` at 12237 mV → **62.4 Wh** at full
  charge.

The honest summary: an idle-but-awake Apple Silicon laptop with the display off
typically sits far below the 8.93 W measured under load, but **this spike did
not measure the idle figure**, and it should be measured once the daemon exists
and the machine is otherwise quiet. What is certain is the qualitative cost:
holding `PreventUserIdleSystemSleep` converts multi-day standby into
hours-scale battery life. **Recommendation: run the Mac on AC whenever the
gateway is armed**, and treat unplugged operation as a temporary mode.

### Limits of this mechanism — must be documented for the operator

`caffeinate -i -s` prevents *idle* sleep. It does **not** prevent:

- **Lid-close (clamshell) sleep.** Lid must stay open, or the Mac must be on
  power with an external display attached.
- An explicit `pmset sleepnow`, the Apple menu → Sleep, or a low-battery
  forced sleep.

`standby 1` and `hibernatemode 3` remain set; they only matter *after* the
system sleeps, which the assertion is there to prevent.

### Verifier

`spikes/assert_awake.sh`, two modes:

- **live** — if `~/.iris/caffeinate.pid` exists (written by the launchd job at
  P7.1), assert that pid is alive *and* currently owns a
  `PreventUserIdleSystemSleep` assertion in `pmset -g assertions`.
- **self-test** — no daemon yet: start `caffeinate -i -s -t 10`, prove the
  assertion appears under that pid, kill it, prove it is released. This proves
  the mechanism works on this machine *and* that it is scoped to the guard's
  lifetime.

Both failure paths were exercised and correctly exit 1: guard pid dead, and
guard pid alive but holding no assertion.

Output of the self-test:

```
$ bash spikes/assert_awake.sh
assert_awake: no /Users/randyren/.iris/caffeinate.pid, running self-test of the mechanism
assert_awake: caffeinate -i -s (pid 95649) holds PreventUserIdleSystemSleep
   pid 95649(caffeinate): [0x00034e8400018feb] 00:00:00 PreventUserIdleSystemSleep named: "caffeinate command-line tool"
	Details: caffeinate asserting for 10 secs
--
   pid 95649(caffeinate): [0x00034e8400078fec] 00:00:00 PreventSystemSleep named: "caffeinate command-line tool"
	Details: caffeinate asserting for 10 secs
assert_awake: PASS - assertion released when the guard exited (scoped to daemon lifetime)
```

### Carried into P7.1

The launchd job must write the caffeinate pid to `~/.iris/caffeinate.pid` so
`spikes/assert_awake.sh` (and later `iris doctor`) can verify it in live mode.

---

## CP-1.1 — chat.db readable

### BLOCKED ON EXTERNAL DEPENDENCY — Full Disk Access not granted

`spikes/read_chatdb.py` is written and ready; it has not been run to a pass
because the read still fails.

Verified at 2026-08-17, immediately before writing this file:

```
$ python3 -c "import sqlite3,pathlib; p=pathlib.Path.home()/'Library/Messages/chat.db'; sqlite3.connect(f'file:{p}?mode=ro',uri=True).execute('select count(*) from message').fetchone()"
sqlite3.OperationalError: unable to open database file
```

The file itself is present and live:

```
$ ls -la ~/Library/Messages/chat.db
-rw-r--r--  1 randyren  staff  991297536 Aug 17 07:05 /Users/randyren/Library/Messages/chat.db
```

**To unblock:** System Settings → Privacy & Security → Full Disk Access → add
the interpreter. Granting it to Terminal/iTerm alone is not enough.

The path in PLAN.md is a symlink chain; all of these resolve to one real
binary, and the FDA picker follows symlinks, so adding any of them should
work:

```
/opt/homebrew/opt/python@3.13/libexec/bin/python3            # what `python3` on PATH is
  -> /opt/homebrew/Cellar/python@3.13/3.13.13_1/Frameworks/Python.framework/Versions/3.13/bin/python3.13
```

If the grant appears to be in place but the read still fails, add the process's
*actual* image, which is not the path above — Homebrew's `python3.13` re-execs
through an app bundle. Confirmed by `ps -o comm=` on a live child:

```
/opt/homebrew/Cellar/python@3.13/3.13.13_1/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python
```

That bundle is **ad-hoc signed** (`codesign -dv` → `flags=0x2(adhoc)`,
`Identifier=org.python.python`, `TeamIdentifier=not set`). Two consequences to
plan around: TCC keys the grant to that unstable identity, and the path
contains the exact Homebrew version `3.13.13_1` — **a `brew upgrade python@3.13`
will move the binary and silently revoke Full Disk Access.** P7.3's `iris
doctor` should therefore check FDA by attempting a real `chat.db` read rather
than by inspecting any grant list.

Then re-run:

```
python3 scripts/checkpoint_runner.py run CP-1.1
```

No checkpoint attempts were spent on CP-1.1 — spending them against a
known-unsatisfiable external precondition would only exhaust `max_attempts: 3`.

`spikes/read_chatdb.py` opens strictly through `file:...?mode=ro`, so SQLite
itself refuses any write; CP-1.1's `does-not-write` check (chat.db mtime
unchanged) is structurally satisfied. Note that Messages writes to this
database continuously, so that check can be perturbed by an inbound message
arriving during the run — a real flake risk to watch, not a defect in the
script.

---

## CP-1.2 — AppleScript can send

### BLOCKED — and A2 is now in doubt for a second, more serious reason

`spikes/send_imessage.sh` and `spikes/assert_sent.py` are written and ready.
`.iris-test-handle` **was created by the operator during this spike** (a valid
E.164 phone number, 13 bytes, one line), so that precondition is now met and
the probe was attempted against the operator's own handle only.

Two blockers stand:

1. **Full Disk Access**, same as CP-1.1 — the `message-lands-in-chatdb` check
   reads `chat.db` to confirm the send. Still not granted.
2. **The Messages AppleScript object model is not responding on this machine.**
   This is new information and it is the bigger risk.

#### Finding: Messages answers app properties but times out on every element

Automation permission is *not* the problem — it is granted, and simple
application properties return instantly:

```
$ osascript -e 'tell application "Messages" to get name'      -> Messages   (0.1s)
$ osascript -e 'tell application "Messages" to get version'   -> 26.0       (0.1s)
```

But **every** access to the scripting object model times out at whatever bound
is set, with `-1712 AppleEvent timed out`:

```
[list services]        exit=1 err='Messages got an error: AppleEvent timed out. (-1712)'  15.1s
[service type filter]  exit=1 err='Messages got an error: AppleEvent timed out. (-1712)'  15.1s
[service id direct]    exit=1 err='Messages got an error: AppleEvent timed out. (-1712)'  15.1s
[accounts]             exit=1 err='Messages got an error: AppleEvent timed out. (-1712)'  15.1s
[chats]                exit=1 err='Messages got an error: AppleEvent timed out. (-1712)'  15.1s
[count services]       exit=1 err='Messages got an error: AppleEvent timed out. (-1712)'  15.1s
```

`spikes/send_imessage.sh` therefore hangs at
`set svc to 1st service whose service type = iMessage`, before it ever reaches
`send`. The first probe attempt was killed at 120 s. **No message was sent** —
the script never got past the service lookup — and no `osascript` process was
left behind.

The error is `-1712` (timed out), *not* `-1743` (not authorised). So this is a
wedged or unimplemented scripting bridge, not a permissions denial.

#### Two candidate causes, and how to tell them apart

- **(a) A wedged Messages.app.** The running instance is pid 22986, up 2h50m
  since `Mon 17 Aug 04:31:35 2026`. A long-lived Messages process going
  unresponsive to Apple Events while still serving basic properties is a
  familiar macOS failure. **Next step: quit and reopen Messages.app, then re-run
  the probes above.** This was deliberately *not* done here — quitting the
  operator's Messages app mid-session is their call, not a spike's.
- **(b) A genuine macOS 26 regression** in the Messages scripting bridge. If the
  timeouts survive a Messages restart *and* a reboot, A2 is disproven in its
  current form and P3.4's sender needs a different mechanism.

#### If (b) — what the fallback would cost

The whole iMessage transport (spec §4.1) depends on being able to *send*;
reading `chat.db` only covers the inbound half. If the AppleScript object model
is permanently dead, the options are, in rough order of preference: drive the
Messages UI via Accessibility/`System Events` keystrokes (fragile, needs the app
frontmost), or change transport. Neither is cheap, which is exactly why this
belongs in P1 rather than being discovered at P3.4.

#### What is already proven about the sender

`spikes/send_imessage.sh` passes the handle and body to `osascript` as `argv`
and never interpolates them into the AppleScript source, so quotes and
backslashes in a message body cannot break out into the script — the same
property CP-3.4 later tests on `iris/sender.py`. Its usage guard exits 2 on
wrong argument count, and `bash -n` is clean.

**To unblock, in this order:**

1. Quit and reopen Messages.app; re-run
   `osascript -e 'with timeout of 15 seconds
   tell application "Messages" to count services
   end timeout'`. It must return a number, not `-1712`.
2. Grant Full Disk Access (see CP-1.1).
3. `python3 scripts/checkpoint_runner.py run CP-1.2`

No checkpoint attempts were spent on CP-1.2 (`attempts=0` of 3), so all three
remain available once the preconditions hold.

Latency is not yet recorded; `spikes/assert_sent.py` prints the observed age of
the sent row, which is the number to paste here once it runs.

---

## Effect on the rest of the plan

- **A3 is disproven in the good direction.** P4.5 should return the
  `https://claude.ai/code/<bridgeSessionId>` link, and `iris/registry.py`
  (P4.4) should populate `remote_control_name` from `bridgeSessionId`, keyed on
  pid — not on the name passed to `--remote-control`.
- **P4.5 must scrub `CLAUDE*` from the child environment** or sessions will not
  register at all, and must handle the workspace-trust prompt.
- **P7.1's launchd job** wraps the daemon in `caffeinate -i -s` and writes
  `~/.iris/caffeinate.pid`.
- **P3 is blocked on the same FDA grant** as CP-1.1 for anything touching the
  real `chat.db`, though the fake-`chat.db` harness (CP-3.1) is deliberately
  designed to need neither FDA nor a phone.
- **A2 is the live risk now, not A3.** PLAN.md rated A3 (Remote Control link)
  as the doubtful one and A2 (AppleScript send) as merely "historically flaky".
  That is inverted by these results: A3 is confirmed true, and A2 could not be
  demonstrated at all because Messages times out on every scripting element.
  Resolve the Messages timeout before starting P3.4 — the sender is on the
  critical path for every success criterion.

---

## Orchestrator Correction — CP-1.2 / A2 (2026-08-17)

**The "A2 is at risk" conclusion above is withdrawn. Sending works.** The
`-1712` timeouts were real but were caused by the *idiom the spike script used*,
not by a wedged Messages.app or a macOS 26 regression. Messages.app was never
restarted; nothing was fixed on the machine.

### What actually breaks, and what doesn't

Re-probed independently. The `service` element is aliased to `account`, but its
accessors are selectively broken:

| Expression | Result |
|---|---|
| `get name of every service` | ❌ `Can't get name of every service` |
| `1st service whose service type = iMessage` | ❌ hangs → `-1712` |
| `get {id, service type} of every account` | ❌ `-10000` (compound record) |
| `get every service` | ✅ returns account ids |
| `get every account` | ✅ returns account ids |
| `get id of 1st account whose service type = iMessage` | ✅ instant → `65CF7048-…` |

Single-property lookups against `account` return instantly. Compound record
requests and `service`-element accessors fail. The spike script used
`1st service whose service type = iMessage`, which is in the failing set — so it
hung before ever reaching `send`.

### The working form

```applescript
tell application "Messages"
    set svc to 1st account whose service type = iMessage
    send msgText to participant targetHandle of svc
end tell
```

`account` not `service`; `participant` not `buddy`.

### Evidence

Two probes sent to the operator's own handle, both `exit=0`, no stderr, no
timeout — one with the corrected idiom inline, one through the repaired
`spikes/send_imessage.sh`. `bash -n` clean.

`spikes/send_imessage.sh` has been fixed and carries a comment explaining why
`account`/`participant` is required.

### Caveat — CP-1.2 is NOT yet passed

`exit=0` from `osascript` proves the send was accepted, **not** that it was
delivered. CP-1.2's `message-lands-in-chatdb` check remains the real proof and
still requires Full Disk Access. Until FDA is granted, CP-1.2 stays BLOCKED and
delivery rests on the operator's visual confirmation.

### Process note

The spike's investigation was sound — it correctly distinguished `-1712`
(timeout) from `-1743` (not authorised), correctly declined to quit the
operator's Messages.app, and correctly documented the fallback cost. Its error
was concluding the object model was dead after testing only `service`-element
expressions. The lesson is to vary the idiom before concluding the platform is
broken.
