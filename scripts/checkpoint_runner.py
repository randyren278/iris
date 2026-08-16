#!/usr/bin/env python3
"""Checkpoint runner for plan-verify-execute project plans.

Extracts ```yaml `checkpoint:` blocks from a plan file, runs their checks,
and gates completion. Designed to back a Claude Code Stop hook (exit 2 blocks
stopping and feeds stderr back to the agent; exit 0 allows the stop) or to
run standalone / in CI.

Usage:
  python scripts/checkpoint_runner.py status              [--plan PLAN.md]
  python scripts/checkpoint_runner.py run CP-1
  python scripts/checkpoint_runner.py next
  python scripts/checkpoint_runner.py gate [--strict]
  python scripts/checkpoint_runner.py approve CP-3
  python scripts/checkpoint_runner.py reset [CP-1]

`expect` grammar: "exit N" asserts the exit code; any other string must
appear in the combined stdout+stderr. Per-check timeout: 600s.
State lives in .checkpoints/state.json. Requires Python 3.8+ and PyYAML.
"""
import argparse
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

STATE = Path(".checkpoints/state.json")
CHECK_TIMEOUT = 600


def die(msg, code=3):
    sys.stderr.write(f"checkpoint_runner: {msg}\n")
    sys.exit(code)


def yaml_mod():
    try:
        import yaml
        return yaml
    except ImportError:
        die("PyYAML is required: pip install pyyaml")


def load_checkpoints(plan):
    p = Path(plan)
    if not p.exists():
        die(f"plan file not found: {plan}")
    yaml = yaml_mod()
    cps, seen = [], set()
    for block in re.findall(r"```yaml\s*\n(.*?)```", p.read_text(encoding="utf-8"), re.S):
        try:
            data = yaml.safe_load(block)
        except Exception:
            continue
        cp = (data or {}).get("checkpoint") if isinstance(data, dict) else None
        if isinstance(cp, dict) and cp.get("id") and cp.get("checks"):
            if cp["id"] in seen:
                die(f"duplicate checkpoint id: {cp['id']}")
            seen.add(cp["id"])
            cps.append(cp)
    if not cps:
        die("no checkpoint blocks found in plan")
    return cps


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2) + "\n")


def entry(state, cid):
    return state.setdefault(cid, {"passed": False, "approved": False, "attempts": 0, "last": None})


def cleared(cp, st):
    ok = st.get("passed", False)
    if cp.get("human_gate"):
        ok = ok and st.get("approved", False)
    return ok


def tail(text, lines=10, chars=1000):
    t = "\n".join(text.strip().splitlines()[-lines:])
    return t[-chars:] if len(t) > chars else t


def run_check(check):
    cmd = check.get("run")
    expect = str(check.get("expect", "exit 0")).strip()
    if not cmd:
        return False, "no run command", ""
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {CHECK_TIMEOUT}s", ""
    out = (p.stdout or "") + (p.stderr or "")
    m = re.fullmatch(r"exit\s+(\d+)", expect)
    if m:
        return p.returncode == int(m.group(1)), f"exit {p.returncode} (expected {expect})", out
    found = expect in out
    return found, ("found expected text" if found else f"missing expected text: {expect!r}"), out


def run_checkpoint(cp, state, stream=None):
    stream = stream or sys.stdout
    st = entry(state, cp["id"])
    st["attempts"] += 1
    maxa = int(cp.get("max_attempts", 3))
    w = stream.write
    w(f"## Checkpoint Report — {cp['id']} ({cp.get('phase', '?')}) — attempt {st['attempts']}/{maxa}\n")
    all_ok = True
    for c in cp.get("checks", []):
        ok, detail, out = run_check(c)
        all_ok = all_ok and ok
        w(f"- {c.get('name', 'unnamed')}: {'PASS' if ok else 'FAIL'} [{detail}]\n")
        w(f"  $ {c.get('run', '')}\n")
        t = tail(out)
        if t:
            w("  " + t.replace("\n", "\n  ") + "\n")
    st["passed"] = all_ok
    st["last"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if all_ok and cp.get("human_gate") and not st["approved"]:
        w(f"Verdict: CHECKS PASS — human approval required: "
          f"python scripts/checkpoint_runner.py approve {cp['id']}\n")
    else:
        w(f"Verdict: {'PASS' if all_ok else 'FAIL'}\n")
    save_state(state)
    return all_ok


def failure_report(cp, st):
    return (f"## Failure Report — {cp['id']} after {st['attempts']} attempts\n"
            f"Checkpoint '{cp.get('phase', '?')}' is still failing at max_attempts. "
            f"Halting per Executor Protocol; a human decision is needed "
            f"(fix, scope change, or correction to the check itself).\n")


def cmd_gate(cps, state, strict):
    pending = [c for c in cps if not cleared(c, entry(state, c["id"]))]
    if not pending:
        print("All checkpoints passed.")
        return 0
    cp = pending[0]
    st = entry(state, cp["id"])
    maxa = int(cp.get("max_attempts", 3))
    if not st["passed"] and st["attempts"] >= maxa:
        sys.stdout.write(failure_report(cp, st))
        return 0  # allow the stop: escalate to the human instead of looping
    if st["passed"] and cp.get("human_gate") and not st["approved"]:
        print(f"{cp['id']} checks passed; awaiting human approval "
              f"(python scripts/checkpoint_runner.py approve {cp['id']}). Allowing stop.")
        return 0
    buf = io.StringIO()
    ok = run_checkpoint(cp, state, stream=buf)
    report = buf.getvalue()
    st = entry(state, cp["id"])
    if ok:
        if cp.get("human_gate") and not st["approved"]:
            sys.stdout.write(report)
            return 0  # safe stop so the human can approve
        rest = [c for c in cps if not cleared(c, entry(state, c["id"]))]
        if strict and rest:
            sys.stderr.write(report + f"\n{cp['id']} passed but the plan is not finished. "
                             f"Next: {rest[0]['id']} ({rest[0].get('phase', '?')}). "
                             f"Continue executing the plan; never modify the checks.\n")
            return 2
        sys.stdout.write(report)
        return 0
    if st["attempts"] >= maxa:
        sys.stdout.write(report + failure_report(cp, st))
        return 0
    sys.stderr.write(report + f"\n{cp['id']} is failing. Fix the work (never the checks) "
                     f"and complete the phase before stopping.\n")
    return 2


def main():
    ap = argparse.ArgumentParser(description="Run and gate plan checkpoints.")
    ap.add_argument("command", choices=["status", "run", "next", "gate", "approve", "reset"])
    ap.add_argument("target", nargs="?", help="checkpoint id, e.g. CP-1")
    ap.add_argument("--plan", default="PLAN.md")
    ap.add_argument("--strict", action="store_true", help="gate: block until ALL checkpoints pass")
    a = ap.parse_args()
    cps = load_checkpoints(a.plan)
    state = load_state()
    by_id = {c["id"]: c for c in cps}

    if a.command == "status":
        for c in cps:
            st = entry(state, c["id"])
            flag = ("PASSED" if cleared(c, st)
                    else "awaiting-approval" if st["passed"]
                    else "pending")
        # noqa: printed below to keep alignment consistent
            print(f"{c['id']:>10}  {flag:<18} attempts={st['attempts']}  {c.get('phase', '')}")
        save_state(state)
        return 0
    if a.command == "approve":
        if not a.target or a.target not in by_id:
            die("approve requires a valid checkpoint id")
        entry(state, a.target)["approved"] = True
        save_state(state)
        print(f"{a.target} approved.")
        return 0
    if a.command == "reset":
        if a.target:
            state.pop(a.target, None)
        else:
            state = {}
        save_state(state)
        print("State reset.")
        return 0
    if a.command == "run":
        if not a.target or a.target not in by_id:
            die("run requires a valid checkpoint id")
        return 0 if run_checkpoint(by_id[a.target], state) else 1
    if a.command == "next":
        pend = [c for c in cps if not cleared(c, entry(state, c["id"]))]
        if not pend:
            print("All checkpoints passed.")
            return 0
        return 0 if run_checkpoint(pend[0], state) else 1
    if a.command == "gate":
        return cmd_gate(cps, state, a.strict)


if __name__ == "__main__":
    sys.exit(main())
