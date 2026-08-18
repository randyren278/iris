from iris.registry import SessionRegistry


def test_registry_uses_replace_and_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "sessions.json"
    SessionRegistry(path, alive=lambda _pid: True).add(tool="claude", pid=100, cwd=tmp_path, prompt="fix")

    assert path.exists()
    assert not path.with_suffix(".tmp").exists()
