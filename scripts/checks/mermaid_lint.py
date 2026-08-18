#!/usr/bin/env python3
"""Structural lint for the mermaid diagrams in the docs.

Rendering is GitHub's job; this catches the failures that survive review — an
empty block, an unknown diagram type, an unbalanced bracket or quote. No
network, no node, binary result.

    python scripts/checks/mermaid_lint.py --min 4 docs/ARCHITECTURE.md
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

FENCE = re.compile(r"^```mermaid\s*$(.*?)^```\s*$", re.MULTILINE | re.DOTALL)
DIAGRAM_TYPES = ("flowchart", "graph", "sequenceDiagram", "stateDiagram-v2", "stateDiagram")
PAIRS = {"[": "]", "(": ")", "{": "}"}


def balanced(body: str) -> str | None:
    """Report the first unbalanced delimiter, ignoring anything inside quotes."""
    stack: list[str] = []
    in_quotes = False
    for character in body:
        if character == '"':
            in_quotes = not in_quotes
            continue
        if in_quotes:
            continue
        if character in PAIRS:
            stack.append(character)
        elif character in PAIRS.values():
            if not stack or PAIRS[stack.pop()] != character:
                return f"unbalanced {character!r}"
    if in_quotes:
        return "unterminated quote"
    if stack:
        return f"unclosed {stack[-1]!r}"
    return None


def lint(path: pathlib.Path, minimum: int) -> list[str]:
    if not path.is_file():
        return [f"{path}: not found"]
    blocks = FENCE.findall(path.read_text())
    problems = []
    if len(blocks) < minimum:
        problems.append(f"{path}: {len(blocks)} mermaid block(s), expected at least {minimum}")
    for index, body in enumerate(blocks, start=1):
        lines = [line for line in body.strip().splitlines() if line.strip()]
        if not lines:
            problems.append(f"{path} block {index}: empty")
            continue
        if not lines[0].strip().startswith(DIAGRAM_TYPES):
            problems.append(f"{path} block {index}: unknown diagram type {lines[0].strip()!r}")
        if len(lines) < 2:
            problems.append(f"{path} block {index}: declares a diagram but draws nothing")
        fault = balanced(body)
        if fault:
            problems.append(f"{path} block {index}: {fault}")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="mermaid_lint")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--min", type=int, default=0,
                        help="minimum mermaid blocks required per file")
    args = parser.parse_args(argv)

    problems = []
    for name in args.files:
        problems.extend(lint(pathlib.Path(name), args.min))
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    print(f"mermaid ok: {' '.join(args.files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
