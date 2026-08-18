#!/bin/bash
# Proves the *actual current working tree* — staged, unstaged, and
# untracked-but-not-ignored files, not just `git HEAD` — installs and passes
# tests from a clean checkout with a fresh venv. CLAUDE.md forbids this
# review from committing, so `git HEAD` alone would miss every uncommitted
# fix; this script snapshots the working tree instead.
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

SNAPSHOT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/iris-clean-clone.XXXXXX")"
SNAPSHOT_BRANCH="iris-review-clean-clone-$$-$(date +%s)"

cleanup() {
    rm -rf "$SNAPSHOT_DIR"
    git branch -D "$SNAPSHOT_BRANCH" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Snapshotting working tree into $SNAPSHOT_DIR"

# `git stash create` builds a commit object of the working tree (index +
# unstaged changes against HEAD) without touching the stash ref or the
# working tree itself. On a clean tree it prints nothing, so fall back to
# HEAD in that case.
STASH_COMMIT="$(git stash create 2>/dev/null || true)"

if [ -n "$STASH_COMMIT" ]; then
    SNAPSHOT_COMMIT="$STASH_COMMIT"
    echo "Local changes detected; snapshotting $SNAPSHOT_COMMIT (git stash create)"
else
    SNAPSHOT_COMMIT="$(git rev-parse HEAD)"
    echo "Working tree matches HEAD; snapshotting $SNAPSHOT_COMMIT"
fi

# `git stash create`'s commit is otherwise unreachable (no ref points to it),
# so a plain `git clone` of $REPO_ROOT would not transfer it. Point a
# throwaway local branch at it so the clone below picks it up as real,
# reachable history — this gives the snapshot a working `.git` (some tests,
# e.g. tests/test_repo_layout.py, shell out to `git ls-files`), unlike a bare
# `git archive | tar -x` snapshot. The branch is deleted in cleanup() above.
git branch -f "$SNAPSHOT_BRANCH" "$SNAPSHOT_COMMIT" >/dev/null
git clone --quiet --local --branch "$SNAPSHOT_BRANCH" --single-branch "$REPO_ROOT" "$SNAPSHOT_DIR"

# `git stash create` / `git archive HEAD` only capture tracked content.
# Overlay untracked-but-not-ignored files (e.g. this review's new tests and
# scripts, never `git add`ed) so the snapshot matches the real working tree.
UNTRACKED_COUNT=0
while IFS= read -r -d '' f; do
    mkdir -p "$SNAPSHOT_DIR/$(dirname "$f")"
    cp "$f" "$SNAPSHOT_DIR/$f"
    UNTRACKED_COUNT=$((UNTRACKED_COUNT + 1))
done < <(git ls-files --others --exclude-standard -z)
echo "Copied $UNTRACKED_COUNT untracked-but-not-ignored file(s) into the snapshot"

PYTHON_BIN="python3.13"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || PYTHON_BIN="python3"

echo "Creating fresh venv with $PYTHON_BIN"
VENV="$SNAPSHOT_DIR/.venv"
"$PYTHON_BIN" -m venv "$VENV"

echo "Installing iris + dev extras (editable)"
if ! ( cd "$SNAPSHOT_DIR" && "$VENV/bin/python" -m pip install -q -e '.[dev]' ); then
    echo "FAILED: pip install -e '.[dev]' in the clean snapshot" >&2
    exit 1
fi

echo "Running pytest -q in the clean snapshot"
if ( cd "$SNAPSHOT_DIR" && "$VENV/bin/python" -m pytest -q ); then
    echo "PASS: clean-clone snapshot installs and its test suite passes."
    exit 0
else
    echo "FAILED: pytest -q in the clean snapshot" >&2
    exit 1
fi
