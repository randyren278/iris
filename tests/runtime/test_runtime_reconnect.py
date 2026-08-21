import time

from iris.runtime import RuntimeSupervisor
from iris.slack import SlackGateway
from tests.slack_fakes import RecordingSlackClient
from tests.gateway.test_slack_echo_e2e import dm_envelope


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
