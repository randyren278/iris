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
