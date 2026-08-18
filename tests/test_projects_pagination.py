from iris.projects import ProjectCatalog


def test_projects_are_paginated_at_a_bounded_page_size(tmp_path):
    for index in range(5):
        (tmp_path / f"project-{index}").mkdir()

    pages = ProjectCatalog.discover(tmp_path).pages(page_size=2)

    assert [len(page) for page in pages] == [2, 2, 1]
