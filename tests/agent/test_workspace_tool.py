import os

import pytest

from iris.tools.workspace import MAX_BYTES, MAX_ENTRIES, WorkspaceInspector, validate_workspace_arguments


def test_workspace_reads_files_and_replaces_invalid_utf8(tmp_path):
    (tmp_path / "note.txt").write_bytes(b"hello\xffworld")
    assert WorkspaceInspector(tmp_path)({"path": "note.txt"}) == {
        "path": "note.txt", "text": "hello�world"
    }


def test_workspace_file_reads_are_bounded(tmp_path):
    (tmp_path / "large.txt").write_text("x" * (MAX_BYTES + 100))
    result = WorkspaceInspector(tmp_path)({"path": "large.txt"})
    assert len(result["text"]) == MAX_BYTES


def test_workspace_lists_sorted_directory_entries_with_cap(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    for index in range(MAX_ENTRIES + 5):
        (folder / f"item-{index:03d}").write_text("x")
    result = WorkspaceInspector(tmp_path)({"path": "folder"})
    assert result["path"] == "folder"
    assert len(result["entries"]) == MAX_ENTRIES
    assert result["entries"] == sorted(result["entries"])


def test_workspace_root_itself_can_be_listed(tmp_path):
    (tmp_path / "a").mkdir()
    assert WorkspaceInspector(tmp_path)({"path": "."}) == {"path": ".", "entries": ["a"]}


def test_workspace_denies_parent_absolute_symlink_escape_and_missing_path(tmp_path):
    outside = tmp_path.parent / f"outside-{tmp_path.name}"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("secret")
    link = tmp_path / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")

    inspector = WorkspaceInspector(tmp_path)
    for path in ("../outside", str(outside / "secret.txt"), "link/secret.txt", "missing.txt"):
        with pytest.raises(ValueError):
            inspector({"path": path})


def test_workspace_schema_requires_exactly_one_text_path():
    assert validate_workspace_arguments({"path": "README.md"}) == {"path": "README.md"}
    for arguments in ({}, {"path": 3}, {"path": "x", "extra": True}):
        with pytest.raises(ValueError, match="path is required"):
            validate_workspace_arguments(arguments)
