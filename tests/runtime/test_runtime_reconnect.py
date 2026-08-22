import time

from iris.runtime import RuntimeSupervisor
from iris.slack import SlackGateway, SocketModeEventSource
from iris.slack_config import SlackCredentials
from tests.slack_fakes import RecordingSlackClient
from tests.gateway.test_slack_echo_e2e import dm_envelope


class FakeSocket:
    """A Socket Mode client whose connection state a test can script."""

    def __init__(self, states):
        self.states = list(states)
        self.polls = 0

    def is_connected(self):
        self.polls += 1
        # The last scripted state persists, which is how a permanent outage looks.
        return self.states[min(self.polls - 1, len(self.states) - 1)]


def supervisor_source(*, stall_timeout=10.0, clock=None):
    """A source whose poll never really sleeps, driven by a scripted clock."""
    ticks = [0.0]

    def tick():
        return ticks[0]

    def advance(_interval):
        ticks[0] += 1.0

    return SocketModeEventSource(
        SlackCredentials("xapp-token", "xoxb-token"),
        poll_interval=1.0, stall_timeout=stall_timeout,
        clock=clock or tick, sleep=advance,
    )


def test_runtime_records_reconnect_and_heartbeat(tmp_path):
    now = [10.0]
    runtime = RuntimeSupervisor(tmp_path, clock=lambda: now[0], pid=lambda: 1)
    assert runtime.start()
    runtime.connected()
    now[0] = 20.0
    runtime.inbound()
    assert runtime.store.read().state == "online"
    assert runtime.store.read().last_inbound_at == 20.0
    runtime.disconnected(RuntimeError())
    assert runtime.store.read().state == "offline"
    runtime.connected()
    assert runtime.store.healthy(max_age=1)


def test_background_heartbeat_refreshes_status_until_close(tmp_path):
    now = [10.0]
    runtime = RuntimeSupervisor(tmp_path, clock=lambda: now[0], pid=lambda: 1)
    assert runtime.start()
    runtime.connected()
    written_at = runtime.store.read().updated_at

    now[0] = 400.0
    # A tiny interval so the loop body runs promptly; close() ends it.
    runtime.start_heartbeat(interval=0.01)
    deadline = time.monotonic() + 5
    while runtime.store.read().updated_at == written_at:
        assert time.monotonic() < deadline, "heartbeat never refreshed runtime status"
        time.sleep(0.01)
    runtime.close()

    # The menu bar treats a stale status file as not-online, so the heartbeat
    # has to keep it fresh while the daemon is otherwise idle.
    assert runtime.store.read().updated_at == 400.0


def test_runtime_starts_just_one_background_heartbeat(tmp_path):
    runtime = RuntimeSupervisor(tmp_path, pid=lambda: 1)
    assert runtime.start()
    runtime.start_heartbeat(interval=100)
    first = runtime._heartbeat_thread
    runtime.start_heartbeat(interval=100)
    assert runtime._heartbeat_thread is first
    runtime.close()


def test_supervisor_reports_each_socket_transition_exactly_once():
    # Down for three polls, then back: the menu bar must learn about both edges,
    # and must not be rewritten on every poll in between.
    socket = FakeSocket([True, True, False, False, False, True, True])
    lifecycle = []
    stops = [False] * 7 + [True]
    supervisor_source().supervise(
        socket, stop=lambda: stops.pop(0),
        on_connected=lambda: lifecycle.append("connected"),
        on_disconnected=lambda: lifecycle.append("disconnected"),
    )
    assert lifecycle == ["disconnected", "connected"]


def test_supervisor_stays_silent_while_the_socket_holds():
    socket = FakeSocket([True])
    lifecycle = []
    stops = [False] * 20 + [True]
    supervisor_source().supervise(
        socket, stop=lambda: stops.pop(0),
        on_connected=lambda: lifecycle.append("connected"),
        on_disconnected=lambda: lifecycle.append("disconnected"),
    )
    assert lifecycle == []


def test_supervisor_returns_when_the_socket_never_comes_back():
    # This is the 1.7-day wedge: slack_sdk kept reconnecting and never
    # succeeded. Returning lets launchd's KeepAlive start a clean process.
    socket = FakeSocket([False])
    lifecycle = []
    # Bounded so a regression that never returns fails fast here instead of
    # hanging the whole suite on an unbounded supervision loop.
    budget = [50]

    def stop():
        budget[0] -= 1
        return budget[0] <= 0

    supervisor_source(stall_timeout=5.0).supervise(
        socket, stop=stop,
        on_connected=lambda: lifecycle.append("connected"),
        on_disconnected=lambda: lifecycle.append("disconnected"),
    )
    assert lifecycle == ["disconnected"]
    # Returned because the stall threshold elapsed, not because the test's own
    # budget ran out.
    assert socket.polls == 6
    assert budget[0] > 40


def test_a_dead_socket_can_no_longer_be_reported_as_online(tmp_path):
    # The regression that made the menu bar lie: the heartbeat kept stamping
    # "online" because nothing ever observed the socket after connect().
    now = [100.0]
    runtime = RuntimeSupervisor(tmp_path, clock=lambda: now[0], pid=lambda: 1)
    assert runtime.start()
    runtime.connected()
    assert runtime.store.healthy()

    stops = [False, True]
    supervisor_source().supervise(FakeSocket([False]), stop=lambda: stops.pop(0),
                                  on_connected=runtime.connected,
                                  on_disconnected=runtime.disconnected)
    runtime.heartbeat()

    assert runtime.store.read().state == "offline"
    assert not runtime.store.healthy()


def test_gateway_marks_accepted_events_and_replies_in_runtime_status(tmp_path):
    runtime = RuntimeSupervisor(tmp_path, pid=lambda: 1)
    assert runtime.start()
    runtime.connected()
    gateway = SlackGateway(["U-allowed"], RecordingSlackClient(),
                           on_inbound=runtime.inbound, on_outbound=runtime.outbound)
    assert gateway.handle_envelope(dm_envelope())
    status = runtime.store.read()
    assert status.last_inbound_at is not None
    assert status.last_outbound_at is not None
