from iris.registry import SessionRegistry


def test_registry_adds_lists_and_removes_sessions(tmp_path):
    registry = SessionRegistry(tmp_path / "sessions.json", alive=lambda _pid: True)
    session = registry.add(tool="claude", pid=100, cwd=tmp_path, prompt="fix it")

    assert registry.sessions() == (session,)
    assert registry.remove(session.id) == session
    assert registry.sessions() == ()
