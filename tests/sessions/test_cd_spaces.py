from iris.projects import ProjectCatalog


def test_cd_match_supports_project_names_with_spaces(tmp_path):
    project = tmp_path / "Second Brain"
    project.mkdir()

    assert ProjectCatalog.discover(tmp_path).select("second brain").path == project.resolve()
