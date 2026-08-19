"""Read-only inspection restricted to one configured workspace root."""
from __future__ import annotations

import pathlib


MAX_BYTES = 32_000
MAX_ENTRIES = 100


def validate_workspace_arguments(arguments: dict[str, object]) -> dict[str, object]:
    if set(arguments) != {"path"} or not isinstance(arguments["path"], str):
        raise ValueError("path is required")
    return arguments


class WorkspaceInspector:
    def __init__(self, root: pathlib.Path | str):
        self.root = pathlib.Path(root).resolve()

    def __call__(self, arguments: dict[str, object]) -> dict[str, object]:
        relative = pathlib.PurePath(str(arguments["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("path escapes workspace")
        target = (self.root / relative).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError("path escapes workspace")
        if target.is_dir():
            return {"path": str(relative), "entries": sorted(item.name for item in target.iterdir())[:MAX_ENTRIES]}
        if not target.is_file():
            raise ValueError("path does not exist")
        return {"path": str(relative), "text": target.read_text(encoding="utf-8", errors="replace")[:MAX_BYTES]}
