import os
import signal
from types import SimpleNamespace

import pytest

from iris.sessions import GatewayDisarmedError, SessionController, _terminate


class Registry:
    def __init__(self):
        self.items = {}
        self.next_id = 1

    def add(self, *, tool, pid, cwd, prompt):
        session = SimpleNamespace(id=self.next_id, tool=tool, pid=pid, cwd=str(cwd), prompt=prompt)
        self.items[session.id] = session
        self.next_id += 1
        return session

    def sessions(self):
        return tuple(self.items.values())

    def remove(self, session_id):
        return self.items.pop(session_id, None)

    def clear(self):
        items = list(self.items.values())
        self.items.clear()
        return items


class Launcher:
    def __init__(self):
        self.calls = []
        self.pid = 91

    def launch(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return SimpleNamespace(pid=self.pid)


class Transport:
    def __init__(self, *, sends=None):
        self.events = []
        self.sends = {} if sends is None else sends

    def register(self, session, process):
        self.events.append(("register", session.id, process.pid))

    def bind_thread(self, session_id, channel_id, thread_ts):
        self.events.append(("bind", session_id, channel_id, thread_ts))

    def send(self, session_id, prompt):
        self.events.append(("send", session_id, prompt))
        return self.sends.get(session_id, True)

    def remove(self, session_id):
        self.events.append(("remove", session_id))


def controller(tmp_path, *, transport=None, disarm=True):
    terminated = []
    instance = SessionController(
        Registry(),
        Launcher(),
        terminator=terminated.append,
        transport=transport,
        disarm_path=(tmp_path / "disarmed") if disarm else None,
    )
    return instance, terminated


def test_launch_without_transport_or_origin_is_minimal(tmp_path):
    sessions, terminated = controller(tmp_path, disarm=False)
    result = sessions.launch("codex", cwd=tmp_path, prompt="work")
    assert result.id == 1
    assert sessions.launcher.calls == [("codex", {"cwd": tmp_path, "prompt": "work"})]
    assert sessions.sessions() == (result,)
    assert terminated == []


def test_launch_with_complete_origin_binds_approval_and_transport_before_initial_claude_prompt(tmp_path):
    transport = Transport()
    sessions, _terminated = controller(tmp_path, transport=transport)
    result = sessions.launch("claude", cwd=tmp_path, prompt="fix", channel_id="D1", thread_ts="1.0")
    assert sessions.launcher.calls == [("claude", {
        "cwd": tmp_path,
        "prompt": "fix",
        "approval_context": ("D1", "1.0"),
    })]
    assert transport.events == [
        ("register", 1, 91),
        ("bind", 1, "D1", "1.0"),
        ("send", 1, "fix"),
    ]
    assert result in sessions.sessions()


def test_partial_origin_does_not_create_approval_context_or_thread_binding(tmp_path):
    transport = Transport()
    sessions, _terminated = controller(tmp_path, transport=transport)
    sessions.launch("codex", cwd=tmp_path, prompt="work", channel_id="D1", thread_ts=None)
    assert sessions.launcher.calls[0][1] == {"cwd": tmp_path, "prompt": "work"}
    assert transport.events == [("register", 1, 91)]


def test_claude_initial_prompt_delivery_failure_rolls_back_everything(tmp_path):
    transport = Transport(sends={1: False})
    sessions, terminated = controller(tmp_path, transport=transport)
    with pytest.raises(RuntimeError, match="unable to deliver the initial prompt"):
        sessions.launch("claude", cwd=tmp_path, prompt="fix", channel_id="D1", thread_ts="1.0")
    assert sessions.sessions() == ()
    assert terminated == [91]
    assert transport.events[-1] == ("remove", 1)


def test_codex_does_not_require_initial_stream_send(tmp_path):
    transport = Transport(sends={1: False})
    sessions, terminated = controller(tmp_path, transport=transport)
    result = sessions.launch("codex", cwd=tmp_path, prompt="work", channel_id="D1", thread_ts="1.0")
    assert result.id == 1
    assert not any(event[0] == "send" for event in transport.events)
    assert terminated == []


def test_existing_disarm_marker_blocks_launch_before_launcher(tmp_path):
    marker = tmp_path / "disarmed"
    marker.write_text("disarmed\n")
    sessions, _terminated = controller(tmp_path)
    assert sessions.disarmed is True
    with pytest.raises(GatewayDisarmedError, match="re-arm from the terminal"):
        sessions.launch("claude", cwd=tmp_path, prompt="x")
    assert sessions.launcher.calls == []


def test_kill_handles_missing_and_live_sessions_with_transport_cleanup(tmp_path):
    transport = Transport()
    sessions, terminated = controller(tmp_path, transport=transport)
    assert sessions.kill(44) is False

    result = sessions.launch("codex", cwd=tmp_path, prompt="work")
    assert sessions.kill(result.id) is True
    assert terminated == [91]
    assert transport.events[-1] == ("remove", result.id)
    assert sessions.sessions() == ()


def test_stop_terminates_all_sessions_persists_private_marker_and_is_idempotent(tmp_path):
    transport = Transport()
    sessions, terminated = controller(tmp_path, transport=transport)
    sessions.launcher.pid = 91
    sessions.launch("codex", cwd=tmp_path, prompt="one")
    sessions.launcher.pid = 92
    sessions.launch("codex", cwd=tmp_path, prompt="two")

    assert sessions.stop() == 2
    assert terminated == [91, 92]
    assert sessions.sessions() == ()
    assert sessions.disarmed is True
    marker = tmp_path / "disarmed"
    assert marker.read_text() == "disarmed\n"
    assert marker.stat().st_mode & 0o777 == 0o600
    assert marker.parent.stat().st_mode & 0o700 == 0o700
    assert [event for event in transport.events if event[0] == "remove"] == [("remove", 1), ("remove", 2)]

    assert sessions.stop() == 0
    assert sessions.disarmed is True


def test_stop_without_persistence_still_disarms_until_terminal_rearm(tmp_path):
    sessions, _terminated = controller(tmp_path, disarm=False)
    sessions.stop()
    assert sessions.disarmed is True
    sessions.rearm_from_terminal()
    assert sessions.disarmed is False


def test_rearm_removes_marker_and_allows_launch_again(tmp_path):
    sessions, _terminated = controller(tmp_path)
    sessions.stop()
    assert (tmp_path / "disarmed").exists()
    sessions.rearm_from_terminal()
    assert sessions.disarmed is False
    assert not (tmp_path / "disarmed").exists()
    assert sessions.launch("codex", cwd=tmp_path, prompt="back").id == 1
    sessions.rearm_from_terminal()  # missing marker remains safe


def test_steer_and_bind_thread_require_transport(tmp_path):
    sessions, _terminated = controller(tmp_path, disarm=False)
    assert sessions.steer(1, "continue") is False
    sessions.bind_thread(1, "D1", "1.0")

    transport = Transport(sends={5: True})
    sessions, _terminated = controller(tmp_path, transport=transport)
    assert sessions.steer(5, "continue") is True
    sessions.bind_thread(5, "D5", "5.0")
    assert transport.events == [("send", 5, "continue"), ("bind", 5, "D5", "5.0")]


def test_default_terminator_sends_sigterm(monkeypatch):
    calls = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: calls.append((pid, sig)))
    _terminate(321)
    assert calls == [(321, signal.SIGTERM)]
