#!/usr/bin/env python3
"""Prove no module under iris/ is silently dead.

Computes the transitive `iris.*` import closure starting from the declared
production entry points (`iris/main.py`, `iris/irisctl.py`,
`iris/approval_hook.py`) plus any module the CLASSIFICATIONS table below
marks as `live-probe` or `operator-cli` (those are run by hand, e.g.
`python -m iris.slack_probe`, so they are entry points in their own right).
Every `.py` file under `iris/` must be either in that closure or have an
entry in CLASSIFICATIONS — otherwise it is a module nothing reaches and
nothing has explained, which is a hard failure.

Note that import-reachability is necessary but not sufficient: a module can
sit in the closure purely because an entry point imports a name it never
constructs. Reaching for this check alone will not catch that.

Usage:
    wiring_audit.py                       # exit 0 if every module is wired
                                           # or classified; else list the
                                           # unclassified orphans and exit 1
    wiring_audit.py --list-orphans        # print one unclassified-orphan
                                           # path per line, nothing else
    wiring_audit.py --check-docs FILE...  # fail if a doc mentions a
                                           # planned-not-wired capability
                                           # without a "not wired" qualifier
                                           # nearby
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
IRIS_ROOT = REPO / "iris"
DECLARED_ENTRY_POINTS = ("iris/main.py", "iris/irisctl.py", "iris/approval_hook.py")

ENTRY_POINT_CLASSIFICATIONS = ("live-probe", "operator-cli")

CLASSIFICATIONS = {
    "iris/slack_probe.py": "live-probe",
    "iris/hook_probe.py": "live-probe",
    "iris/agent_probe.py": "live-probe",
    "iris/weather_probe.py": "live-probe",
    "iris/web_probe.py": "live-probe",
    "iris/senses/calendar_probe.py": "live-probe",
    "iris/salience.py": "planned-not-wired",
    "iris/user_model.py": "planned-not-wired",
    "iris/outcomes.py": "planned-not-wired",
    "iris/capabilities.py": "planned-not-wired",
    "iris/lanes.py": "planned-not-wired",
    "iris/hera_memory.py": "planned-not-wired",
    "iris/fallback.py": "planned-not-wired",
}

# --- Doc-claim heuristic -------------------------------------------------
# This is deliberately not linguistically perfect, just directionally
# correct: each `planned-not-wired` module is mapped to the handful of words
# a doc would realistically use to describe its capability, the doc is split
# into paragraph/bullet/table-row "blocks" (fenced code blocks, including
# mermaid diagrams, are skipped entirely — diagram labels are not prose
# claims, and editing them risks the separate mermaid-lint check), and any
# block that mentions a keyword must also contain a "not wired" style
# qualifier phrase.
MODULE_DOC_KEYWORDS = {
    "iris/senses/__init__.py": ["quarantine"],
    "iris/salience.py": ["salience"],
    "iris/user_model.py": ["user-model", "user model"],
    "iris/capabilities.py": ["capability policy"],
    "iris/lanes.py": ["session lanes"],
    "iris/outcomes.py": ["outcome ledger"],
    "iris/hera_memory.py": ["hera memory", "hera source"],
    "iris/fallback.py": ["fallback translator", "natural-language fallback"],
}

QUALIFIER_PHRASES = (
    "not wired",
    "not yet wired",
    "not currently wired",
    "planned",
    "scaffolding",
    "not automatically",
    "does not run",
    "not invoked",
)


def _module_name_to_path(name: str) -> pathlib.Path | None:
    """Resolve a dotted `iris...` module name to a file under iris/, if any.

    A package (`iris/foo/__init__.py`) always wins over a same-named sibling
    module (`iris/foo.py`) — that is real Python import resolution, not a
    simplification (verified live: `import iris.senses` resolves to
    `iris/senses/__init__.py` even though `iris/senses.py` also exists).
    """
    if name != "iris" and not name.startswith("iris."):
        return None
    parts = name.split(".")[1:]
    if not parts:
        return IRIS_ROOT / "__init__.py"
    base = IRIS_ROOT.joinpath(*parts)
    candidate_package = base / "__init__.py"
    if candidate_package.is_file():
        return candidate_package
    candidate_module = base.with_suffix(".py")
    if candidate_module.is_file():
        return candidate_module
    return None


def _imported_iris_modules(tree: ast.AST) -> set[str]:
    """All `iris...` dotted module names imported anywhere in the tree.

    Uses ast.walk (not ast.iter_child_nodes) so imports nested inside a
    function body — e.g. most of what `main()` imports — are still found.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "iris" or alias.name.startswith("iris."):
                    names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module:
                continue
            if node.module == "iris" or node.module.startswith("iris."):
                names.add(node.module)
                # `from iris.pkg import submodule` may import a submodule
                # file directly rather than a name defined in __init__.py.
                for alias in node.names:
                    names.add(f"{node.module}.{alias.name}")
    return names


def compute_closure(entry_points: list[pathlib.Path]) -> set[pathlib.Path]:
    closure: set[pathlib.Path] = set()
    queue = list(entry_points)
    while queue:
        path = queue.pop()
        if path in closure or not path.is_file():
            continue
        closure.add(path)
        tree = ast.parse(path.read_text(), filename=str(path))
        for name in _imported_iris_modules(tree):
            resolved = _module_name_to_path(name)
            if resolved is not None and resolved not in closure:
                queue.append(resolved)
                parent = resolved.parent
                while parent != IRIS_ROOT.parent:
                    init_py = parent / "__init__.py"
                    if init_py.is_file() and init_py not in closure:
                        queue.append(init_py)
                    if parent == IRIS_ROOT:
                        break
                    parent = parent.parent
    return closure


def all_iris_modules() -> list[pathlib.Path]:
    modules = []
    for path in sorted(IRIS_ROOT.rglob("*.py")):
        if path.name == "__init__.py" and not path.read_text().strip():
            continue
        modules.append(path)
    return modules


def find_orphans() -> tuple[list[pathlib.Path], dict[str, str]]:
    classifications = CLASSIFICATIONS
    entry_points = [REPO / p for p in DECLARED_ENTRY_POINTS]
    for rel, classification in classifications.items():
        if classification in ENTRY_POINT_CLASSIFICATIONS:
            entry_points.append(REPO / rel)
    closure = compute_closure(entry_points)
    orphans = []
    for module in all_iris_modules():
        if module in closure:
            continue
        rel = module.relative_to(REPO).as_posix()
        if rel in classifications:
            continue
        orphans.append(module)
    return orphans, classifications


def _doc_blocks(text: str) -> list[str]:
    """Split doc text into paragraph/bullet/table-row blocks, skipping fenced code."""
    blocks: list[str] = []
    current: list[str] = []
    in_code = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        if in_code:
            continue
        starts_new_block = (
            not stripped
            or line.startswith("- ")
            or line.startswith("#")
            or (stripped.startswith("|") and stripped.endswith("|"))
        )
        if starts_new_block and current:
            blocks.append("\n".join(current))
            current = []
        if stripped:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _check_docs(paths: list[pathlib.Path]) -> int:
    classifications = CLASSIFICATIONS
    planned = [module for module, c in classifications.items() if c == "planned-not-wired"]
    failures = []
    for doc_path in paths:
        if not doc_path.is_file():
            failures.append(f"{doc_path}: file not found")
            continue
        blocks = _doc_blocks(doc_path.read_text())
        normalized_blocks = [(block, " ".join(block.split()).lower()) for block in blocks]
        for module in planned:
            for keyword in MODULE_DOC_KEYWORDS.get(module, []):
                for block, normalized in normalized_blocks:
                    if keyword not in normalized:
                        continue
                    if not any(qualifier in normalized for qualifier in QUALIFIER_PHRASES):
                        failures.append(
                            f"{doc_path}: mentions '{keyword}' (from {module}) without a "
                            f"'not wired' qualifier nearby:\n    {block.strip()[:200]}"
                        )
    if failures:
        print("Docs claim planned-not-wired capabilities without qualifiers:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-orphans", action="store_true",
                        help="print one unclassified-orphan path per line, nothing else")
    parser.add_argument("--check-docs", nargs="+", metavar="FILE",
                        help="fail if a doc claims a planned-not-wired module is live")
    args = parser.parse_args(argv)

    if args.check_docs:
        return _check_docs([pathlib.Path(f) for f in args.check_docs])

    orphans, _classifications = find_orphans()

    if args.list_orphans:
        for module in orphans:
            print(module.relative_to(REPO).as_posix())
        return 0

    if orphans:
        print("Unwired iris/ modules with no entry in wiring_audit CLASSIFICATIONS:",
              file=sys.stderr)
        for module in orphans:
            print(f"  {module.relative_to(REPO).as_posix()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
