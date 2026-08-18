from iris.projects import ProjectCatalog


def test_cd_fuzzy_match_selects_one_project(tmp_path):
    project = tmp_path / "Iris Gateway"
    project.mkdir()
    (tmp_path / "Hera").mkdir()

    assert ProjectCatalog.discover(tmp_path).select("gateway").path == project.resolve()
