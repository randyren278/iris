"""Safe local project discovery and deterministic fuzzy selection."""
from __future__ import annotations

import dataclasses
import pathlib
import re


@dataclasses.dataclass(frozen=True)
class Project:
    name: str
    path: pathlib.Path


class ProjectQueryError(ValueError):
    """A project query could not safely select exactly one project."""


def _normalise(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def _is_safe_query(query: str) -> bool:
    if not isinstance(query, str) or not query.strip():
        return False
    path = pathlib.PurePath(query)
    return not path.is_absolute() and ".." not in path.parts and "/" not in query and "\\" not in query


class ProjectCatalog:
    """An immutable index of direct child project directories beneath one root."""

    def __init__(self, root: pathlib.Path, projects: tuple[Project, ...]):
        self.root = root.resolve()
        self.projects = projects

    @classmethod
    def discover(cls, root: pathlib.Path | str) -> ProjectCatalog:
        safe_root = pathlib.Path(root).expanduser().resolve()
        if not safe_root.is_dir():
            raise ProjectQueryError("project root is not a directory")
        projects = tuple(
            Project(path.name, path.resolve())
            for path in sorted(safe_root.iterdir(), key=lambda item: item.name.casefold())
            if path.is_dir() and not path.is_symlink() and not path.name.startswith(".")
        )
        return cls(safe_root, projects)

    def pages(self, *, page_size: int = 10) -> tuple[tuple[Project, ...], ...]:
        if page_size < 1:
            raise ValueError("page_size must be positive")
        return tuple(self.projects[offset:offset + page_size]
                     for offset in range(0, len(self.projects), page_size))

    def select(self, query: str) -> Project:
        if not _is_safe_query(query):
            raise ProjectQueryError("project query must be a project name, not a path")
        needle = _normalise(query)
        exact = [project for project in self.projects if _normalise(project.name) == needle]
        if len(exact) == 1:
            return exact[0]
        matches = [project for project in self.projects if needle in _normalise(project.name)]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ProjectQueryError("no matching project")
        raise ProjectQueryError("ambiguous project query")
