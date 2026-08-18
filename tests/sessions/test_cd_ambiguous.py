import pytest

from iris.projects import ProjectCatalog, ProjectQueryError


def test_cd_ambiguous_match_never_guesses(tmp_path):
    (tmp_path / "Iris Gateway").mkdir()
    (tmp_path / "Iris Memory").mkdir()

    with pytest.raises(ProjectQueryError, match="ambiguous"):
        ProjectCatalog.discover(tmp_path).select("iris")
