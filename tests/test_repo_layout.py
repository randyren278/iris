"""The repository root should stay legible, and doc links should resolve.

Root clutter accumulates one harmless file at a time. This pins the intended
set so the next addition is a deliberate decision.
"""
import pathlib
import re
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[1]
ROOT_FILES = {".gitignore", "README.md", "pyproject.toml"}


def tracked_files():
    listing = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True,
                             check=True)
    return listing.stdout.splitlines()


def test_repository_root_holds_only_the_intended_files():
    root = {path for path in tracked_files() if "/" not in path}
    assert root == ROOT_FILES


def test_markdown_links_and_images_resolve():
    """Moving assets under docs/ must not leave a dangling reference."""
    broken = []
    for document in [REPO / "README.md", *(REPO / "docs").rglob("*.md")]:
        text = document.read_text()
        targets = re.findall(r'!?\[[^\]]*\]\(([^)#]+)\)', text)
        targets += re.findall(r'<img src="([^"]+)"', text)
        for target in targets:
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (document.parent / target).resolve().exists():
                broken.append(f"{document.name} -> {target}")
    assert not broken, f"unresolved links: {broken}"


def test_no_duplicate_test_basenames():
    """tests/ has no __init__.py, so two same-named modules would collide."""
    names = [pathlib.PurePath(path).name for path in tracked_files()
             if path.startswith("tests/") and path.endswith(".py")]
    duplicates = {name for name in names if names.count(name) > 1}
    assert not duplicates, f"duplicate test module names: {duplicates}"
