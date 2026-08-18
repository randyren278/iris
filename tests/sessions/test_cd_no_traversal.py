import pytest

from iris.projects import ProjectCatalog, ProjectQueryError


@pytest.mark.parametrize("query", ["../outside", "/tmp/outside", "one/two", r"one\\two"])
def test_cd_rejects_path_traversal_and_paths(tmp_path, query):
    (tmp_path / "iris").mkdir()

    with pytest.raises(ProjectQueryError, match="not a path"):
        ProjectCatalog.discover(tmp_path).select(query)
