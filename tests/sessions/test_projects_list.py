from iris.projects import ProjectCatalog


def test_discovers_sorted_non_hidden_direct_child_directories(tmp_path):
    (tmp_path / "zeta").mkdir()
    (tmp_path / "Alpha").mkdir()
    (tmp_path / ".cache").mkdir()
    (tmp_path / "readme.txt").write_text("not a project")

    catalog = ProjectCatalog.discover(tmp_path)

    assert [project.name for project in catalog.projects] == ["Alpha", "zeta"]
