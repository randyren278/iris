from iris.registry import SessionRegistry


def test_registry_survives_a_reload(tmp_path):
    path = tmp_path / "sessions.json"
    first = SessionRegistry(path, alive=lambda _pid: True)
    created = first.add(tool="codex", pid=101, cwd=tmp_path, prompt="document")

    restored = SessionRegistry(path, alive=lambda _pid: True)

    assert restored.sessions() == (created,)
