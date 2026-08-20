"""Mutation-test the invariants in CLAUDE.md against the pytest suite.

For each entry in a mutations manifest (id, file, find, replace, invariant):
break the invariant in-place, run the suite, and require it to go red. A
mutation the suite does not catch (SURVIVED) means the invariant is
unguarded. The mutated file is always restored, even on failure.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# A mutation that removes a guard rail can leave a test waiting on something
# that will now never happen. Without a bound the suite hangs, the whole job is
# killed by the CI timeout, and the log shows no verdict at all -- so cap each
# run well above the honest suite runtime and report the hang as its own class.
RUN_TIMEOUT_SECONDS = 120.0


class ManifestError(RuntimeError):
    pass


def _run(args, **kwargs):
    return subprocess.run(args, cwd=REPO_ROOT, check=False,
                           capture_output=True, text=True, **kwargs)


def load_manifest(manifest_path: pathlib.Path) -> list[dict]:
    data = yaml.safe_load(manifest_path.read_text())
    mutations = data.get("mutations") if isinstance(data, dict) else None
    if not mutations:
        raise ManifestError(f"{manifest_path} has no 'mutations' list")
    for entry in mutations:
        missing = {"id", "file", "find", "replace", "invariant"} - entry.keys()
        if missing:
            raise ManifestError(f"mutation {entry.get('id', '?')} missing fields: {missing}")
    return mutations


def apply_mutation(entry: dict) -> tuple[str, str]:
    """Apply one mutation, run pytest, restore the file.

    Returns (status, detail) where status is one of:
      "killed"   -- find matched once, mutation applied, suite went red (good).
      "survived" -- find matched once, mutation applied, suite stayed green
                    (the invariant is unguarded by any test).
      "timeout"  -- the suite neither passed nor failed within
                    RUN_TIMEOUT_SECONDS. A test is waiting on something the
                    mutation prevents. That is a non-deterministic suite
                    defect, not a kill: bound the wait so the test fails fast.
      "stale"    -- find did not match exactly once. The manifest text no
                    longer matches iris/ (usually because a legitimate fix
                    changed the surrounding source) -- this is a manifest
                    maintenance problem, not evidence the invariant is
                    unguarded, and must not be conflated with "survived".
    """
    target = REPO_ROOT / entry["file"]
    original = target.read_text()
    count = original.count(entry["find"])
    if count != 1:
        return "stale", (
            f"'find' matched {count} times in {entry['file']} (need exactly 1) -- "
            "manifest entry no longer matches the current source; update find/replace"
        )
    mutated = original.replace(entry["find"], entry["replace"], 1)
    try:
        target.write_text(mutated)
        try:
            result = _run([sys.executable, "-m", "pytest", "-q", "-x"],
                          timeout=RUN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return "timeout", (
                f"pytest did not finish within {RUN_TIMEOUT_SECONDS:.0f}s -- a test is "
                "blocking on a condition this mutation prevents; give that wait a bound "
                "so it fails fast instead of hanging")
        if result.returncode == 0:
            return "survived", "pytest exited 0 (suite stayed green) -- SURVIVED"
        return "killed", f"pytest exited {result.returncode} -- KILLED"
    finally:
        target.write_text(original)
        if target.read_text() != original:
            raise ManifestError(
                f"failed to restore {entry['file']} to its original content after mutation "
                f"{entry['id']!r}; on-disk content does not match the pre-mutation snapshot")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=pathlib.Path, required=True)
    parser.add_argument("--assert-min", type=int, default=0,
                         help="fail unless at least this many mutations were run")
    args = parser.parse_args(argv)

    try:
        mutations = load_manifest(args.manifest)
    except ManifestError as error:
        print(f"MANIFEST ERROR: {error}")
        return 1

    rows = []
    survived = 0
    stale = 0
    timed_out = 0
    for entry in mutations:
        try:
            status, detail = apply_mutation(entry)
        except ManifestError as error:
            print(f"MANIFEST ERROR on {entry['id']}: {error}", flush=True)
            return 1
        verdict = status.upper()
        if status == "survived":
            survived += 1
        elif status == "stale":
            stale += 1
        elif status == "timeout":
            timed_out += 1
        rows.append((entry["id"], entry["file"], verdict, detail))
        # Flush per mutation: CI captures stdout through a pipe, so without this
        # a run that dies part way through shows no verdicts at all.
        print(f"{verdict:9s} {entry['id']:32s} {entry['file']}", flush=True)

    print()
    print(f"{'id':32s} {'file':24s} verdict")
    print("-" * 72)
    for mutation_id, file, verdict, detail in rows:
        print(f"{mutation_id:32s} {file:24s} {verdict}")
        if verdict in ("STALE", "TIMEOUT"):
            print(f"  {detail}")

    total = len(rows)
    killed = total - survived - stale - timed_out
    print()
    print(f"{total} mutations run, {killed} killed, {survived} survived, "
          f"{stale} stale, {timed_out} timed out", flush=True)

    if total < args.assert_min:
        print(f"FAIL: only {total} mutations ran, expected at least {args.assert_min}")
        return 1
    if stale:
        print(f"FAIL: {stale} manifest entry(ies) no longer match the current source -- "
              f"update find/replace in the manifest, this is not evidence of an unguarded invariant")
        return 1
    if timed_out:
        print(f"FAIL: {timed_out} mutation(s) hung the suite instead of failing it -- "
              f"bound the blocking wait so the invariant is proven by a fast failure")
        return 1
    if survived:
        print(f"FAIL: {survived} mutation(s) survived (invariant unguarded by tests)")
        return 1
    print("PASS: all mutations killed")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    raise SystemExit(main())
