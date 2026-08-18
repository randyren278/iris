"""CP-3.2: a restart resumes, it does not replay."""
import json

from iris.poller import Poller


def test_no_replay_after_restart(fakedb, tmp_path):
    state = tmp_path / "state.json"
    first = Poller(fakedb.path, state)
    first.poll_once()

    fakedb.inject("+15551234567", "seen before restart")
    assert len(first.poll_once()) == 1

    restarted = Poller(fakedb.path, state)
    assert restarted.poll_once() == [], "restart replayed an old message"


def test_messages_arriving_while_down_are_delivered(fakedb, tmp_path):
    """Resuming must not skip messages that arrived during the outage."""
    state = tmp_path / "state.json"
    first = Poller(fakedb.path, state)
    first.poll_once()

    fakedb.inject("+15551234567", "sent while iris was down")
    restarted = Poller(fakedb.path, state)
    assert [m.body for m in restarted.poll_once()] == ["sent while iris was down"]


def test_high_water_is_persisted_to_disk(fakedb, tmp_path):
    state = tmp_path / "state.json"
    poller = Poller(fakedb.path, state)
    poller.poll_once()
    rowid = fakedb.inject("+15551234567", "one")
    poller.poll_once()
    assert json.loads(state.read_text())["high_water"] == rowid


def test_corrupt_state_file_does_not_replay_history(fakedb, tmp_path):
    """Unreadable state must fail safe: resume at the tip, not at row 0."""
    state = tmp_path / "state.json"
    state.write_text("{ this is not json")
    for n in range(3):
        fakedb.inject("+15551234567", f"old {n}")
    poller = Poller(fakedb.path, state)
    assert poller.poll_once() == []


def test_state_directory_is_created(fakedb, tmp_path):
    state = tmp_path / "nested" / "dir" / "state.json"
    Poller(fakedb.path, state).poll_once()
    assert state.exists()
