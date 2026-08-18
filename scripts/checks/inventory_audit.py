#!/usr/bin/env python3
"""Assert every iris/**/*.py file appears exactly once in .review/inventory.md."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INVENTORY = Path(".review/inventory.md")
ROW_PATH = re.compile(r"^\|\s*(iris/[^\s|]+\.py)\s*\|")


def table_paths(text: str) -> list[str]:
    return [match.group(1) for line in text.splitlines() if (match := ROW_PATH.match(line))]


def table_rows(text: str) -> list[str]:
    return [line for line in text.splitlines() if ROW_PATH.match(line)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-reviewed", action="store_true",
                        help="also require a Reviewed column/marker per row (populated in a later phase)")
    args = parser.parse_args()

    if not INVENTORY.exists():
        sys.stderr.write(f"missing {INVENTORY}\n")
        return 1

    text = INVENTORY.read_text(encoding="utf-8")
    paths = table_paths(text)
    on_disk = sorted(str(p) for p in Path("iris").rglob("*.py"))

    counts: dict[str, int] = {}
    for path in paths:
        counts[path] = counts.get(path, 0) + 1

    missing = [path for path in on_disk if counts.get(path, 0) == 0]
    duplicated = sorted(path for path, count in counts.items() if count > 1)
    unknown = sorted(path for path in counts if path not in on_disk)

    ok = True
    if missing:
        ok = False
        sys.stderr.write("missing from inventory:\n" + "\n".join(f"  {p}" for p in missing) + "\n")
    if duplicated:
        ok = False
        sys.stderr.write("duplicated in inventory:\n" + "\n".join(f"  {p}" for p in duplicated) + "\n")
    if unknown:
        ok = False
        sys.stderr.write("inventory references files not found on disk:\n" +
                         "\n".join(f"  {p}" for p in unknown) + "\n")

    if args.require_reviewed:
        header = next((line for line in text.splitlines() if line.strip().startswith("| Path")), None)
        if header is None or "Reviewed" not in header:
            ok = False
            sys.stderr.write("--require-reviewed: inventory table has no 'Reviewed' column yet\n")
        else:
            columns = [c.strip() for c in header.strip().strip("|").split("|")]
            reviewed_index = columns.index("Reviewed")
            unreviewed = []
            for row in table_rows(text):
                cells = [c.strip() for c in row.strip().strip("|").split("|")]
                if reviewed_index >= len(cells) or not cells[reviewed_index]:
                    unreviewed.append(cells[0] if cells else row)
            if unreviewed:
                ok = False
                sys.stderr.write("--require-reviewed: rows with an empty Reviewed cell:\n" +
                                 "\n".join(f"  {p}" for p in unreviewed) + "\n")

    if not ok:
        return 1

    print(f"inventory covers all {len(on_disk)} iris/**/*.py files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
