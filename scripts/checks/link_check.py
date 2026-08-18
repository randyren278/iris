#!/usr/bin/env python3
"""Assert every relative markdown link target resolves to a real file.

For each given markdown file, finds `[text](target)` links, skips absolute
URLs (http/https), strips any `#anchor` suffix (anchors are not validated),
and checks the remaining path resolves relative to the linking file's own
directory.

Usage:
    python scripts/checks/link_check.py FILE [FILE ...]
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def broken_links(path: pathlib.Path) -> list[str]:
    broken = []
    text = path.read_text()
    for target in LINK.findall(text):
        target = target.strip()
        if target.startswith("http://") or target.startswith("https://"):
            continue
        file_part = target.split("#", 1)[0]
        if not file_part:
            continue
        resolved = (path.parent / file_part).resolve()
        if not resolved.is_file():
            broken.append(f"{path}: '{target}' -> {resolved} does not exist")
    return broken


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=pathlib.Path)
    args = parser.parse_args(argv)

    failures = []
    for path in args.files:
        if not path.is_file():
            failures.append(f"{path}: file not found")
            continue
        failures.extend(broken_links(path))

    if failures:
        print("Broken relative markdown links:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print(f"link check ok: {' '.join(str(f) for f in args.files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
