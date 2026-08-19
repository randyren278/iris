import pytest

from iris.tools.workspace import WorkspaceInspector, validate_workspace_arguments


def test_workspace_reads_only_beneath_configured_root(tmp_path):
    (tmp_path / "note.txt").write_text("hello")
    assert WorkspaceInspector(tmp_path)({"path": "note.txt"}) == {"path": "note.txt", "text": "hello"}
    with pytest.raises(ValueError):
        WorkspaceInspector(tmp_path)({"path": "../outside"})


def test_workspace_schema_requires_a_single_text_path():
    with pytest.raises(ValueError):
        validate_workspace_arguments({"path": 3})
