from iris.registry import SessionRegistry


def test_registry_reaps_dead_processes_on_load(tmp_path):
    path = tmp_path / "sessions.json"
    SessionRegistry(path, alive=lambda _pid: True).add(tool="claude", pid=999, cwd=tmp_path, prompt="stale")

    restored = SessionRegistry(path, alive=lambda _pid: False)

    assert restored.sessions() == ()
