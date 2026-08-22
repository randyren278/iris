from types import SimpleNamespace

import pytest

import iris.agent_actions as action_module
import iris.agent_conversation as conversation_module
import iris.approvals as approvals_module
import iris.doctor as doctor_module
import iris.launcher as launcher_module
import iris.main as main_module
import iris.runtime as runtime_module
import iris.session_transport as session_transport_module
import iris.sessions as sessions_module
import iris.slack as slack_module
import iris.slack_config as slack_config_module
from iris.config import Config


class RecordingRuntime:
    instances = []
    start_result = True

    def __init__(self, state_dir):
        self.state_dir = state_dir
        self.events = []
        self.__class__.instances.append(self)

    def start(self):
        self.events.append("start")
        return self.start_result

    def start_heartbeat(self):
        self.events.append("heartbeat")

    def inbound(self):
        self.events.append("inbound")

    def outbound(self):
        self.events.append("outbound")

    def connected(self):
        self.events.append("connected")

    def disconnected(self, error=None):
        self.events.append(("disconnected", type(error).__name__ if error else None))

    def close(self):
        self.events.append("close")


class RecordingClient:
    instances = []

    def __init__(self, token):
        self.token = token
        self.posts = []
        self.__class__.instances.append(self)

    def post_message(self, **kwargs):
        self.posts.append(kwargs)


class FakeApprovalQueue:
    def __init__(self, *, notifier):
        self.notifier = notifier
        try:
            notifier("unbound probe")
        except RuntimeError as error:
            assert "no Slack origin" in str(error)

    def resolve(self, *_args, **_kwargs):
        return False


class RecordingApprovalServer:
    instances = []

    def __init__(self, path, queue, *, notifier_for_context):
        self.path = path
        self.queue = queue
        self.notifier_for_context = notifier_for_context
        self.events = []
        self.__class__.instances.append(self)

    def start(self):
        self.events.append("start")

    def close(self):
        self.events.append("close")


class RecordingActionServer:
    instances = []

    def __init__(self, path, approvals, projects, sessions, *, notifier_for_context):
        self.path = path
        self.approvals = approvals
        self.projects = projects
        self.sessions = sessions
        self.events = []
        self.__class__.instances.append(self)
        notifier_for_context("D1", "1.0")("approval from action server")

    def start(self):
        self.events.append("start")

    def close(self):
        self.events.append("close")


class FakeLauncher:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class RecordingTransport:
    instances = []

    def __init__(self, notifier):
        self.notifier = notifier
        self.__class__.instances.append(self)


class FakeSessionController:
    instances = []

    def __init__(self, registry, launcher, *, transport, disarm_path):
        self.registry = registry
        self.launcher = launcher
        self.transport = transport
        self.disarm_path = disarm_path
        self.__class__.instances.append(self)

    def sessions(self):
        return ()


class RecordingAdapter:
    instances = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.__class__.instances.append(self)


class FakeCoordinator:
    def __init__(self, runtime, agent_factory, *, context_provider):
        self.runtime = runtime
        self.agent_factory = agent_factory
        self.context_provider = context_provider
        assert context_provider(("D1", "1.0"), "anything") == ()
        message = SimpleNamespace(channel_id="D1", reply_thread_ts="1.0")
        self.agent = agent_factory(message, (), ())

    def reply(self, _message):
        return "conversation"


class RecordingSlackGateway:
    instances = []

    def __init__(self, allowlist, client, *, handler, audit, on_inbound, on_outbound):
        self.allowlist = tuple(allowlist)
        self.client = client
        self.handler = handler
        self.audit = audit
        self.on_inbound = on_inbound
        self.on_outbound = on_outbound
        self.responses = []
        self.__class__.instances.append(self)

    def handle_envelope(self, _envelope):
        self.on_inbound()
        message = SimpleNamespace(
            text="projects",
            channel_id="D1",
            reply_thread_ts="1.0",
            thread_ts=None,
        )
        self.responses.append(self.handler(message))
        self.on_outbound()
        return True


class RecordingSource:
    instances = []
    error = None

    def __init__(self, credentials):
        self.credentials = credentials
        self.__class__.instances.append(self)

    def run(self, handler, *, on_connected, on_disconnected):
        on_connected()
        handler({"type": "probe"})
        if self.error:
            on_disconnected(self.error)
            raise self.error
        on_disconnected()


def install_fakes(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "Alpha").mkdir()
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    main_module.load = lambda: Config(slack_allowlist=("U1",), projects_root=projects)
    monkeypatch.setattr(slack_config_module, "load_credentials",
                        lambda: SimpleNamespace(bot_token="xoxb-test", app_token="xapp-test"))
    monkeypatch.setattr(doctor_module, "ensure_private_state_dir", lambda _path: state_dir)
    monkeypatch.setattr(runtime_module, "RuntimeSupervisor", RecordingRuntime)
    monkeypatch.setattr(slack_module, "SlackWebClient", RecordingClient)
    monkeypatch.setattr(slack_module, "SlackGateway", RecordingSlackGateway)
    monkeypatch.setattr(slack_module, "SocketModeEventSource", RecordingSource)
    monkeypatch.setattr(approvals_module, "ApprovalQueue", FakeApprovalQueue)
    monkeypatch.setattr(approvals_module, "ApprovalServer", RecordingApprovalServer)
    monkeypatch.setattr(action_module, "AgentActionServer", RecordingActionServer)
    monkeypatch.setattr(launcher_module, "Launcher", FakeLauncher)
    monkeypatch.setattr(sessions_module, "SessionController", FakeSessionController)
    monkeypatch.setattr(session_transport_module, "SessionTransport", RecordingTransport)
    monkeypatch.setattr(conversation_module, "ClaudeToolAgentAdapter", RecordingAdapter)
    monkeypatch.setattr(conversation_module, "GeneralAgentCoordinator", FakeCoordinator)
    return projects, state_dir


def reset_fakes():
    for cls in (RecordingRuntime, RecordingClient, RecordingApprovalServer, RecordingActionServer,
                FakeSessionController, RecordingAdapter, RecordingSlackGateway, RecordingSource,
                RecordingTransport):
        cls.instances.clear()
    RecordingRuntime.start_result = True
    RecordingSource.error = None


def test_main_composes_current_agentic_daemon_and_cleans_up(monkeypatch, tmp_path):
    reset_fakes()
    projects, state_dir = install_fakes(monkeypatch, tmp_path)

    main_module.main()

    runtime = RecordingRuntime.instances[-1]
    assert runtime.state_dir == state_dir
    assert runtime.events == ["start", "heartbeat", "outbound", "connected", "inbound", "outbound",
                              ("disconnected", None), "close"]
    assert RecordingClient.instances[-1].token == "xoxb-test"
    assert RecordingClient.instances[-1].posts == [{
        "channel_id": "D1", "thread_ts": "1.0", "text": "approval from action server"
    }]
    assert RecordingApprovalServer.instances[-1].events == ["start", "close"]
    assert RecordingActionServer.instances[-1].events == ["start", "close"]
    assert FakeSessionController.instances[-1].disarm_path == state_dir / "disarmed"
    assert RecordingSlackGateway.instances[-1].responses == ["Projects: Alpha"]
    adapter = RecordingAdapter.instances[-1]
    assert adapter.args[0] == projects
    assert adapter.kwargs == {
        "action_socket": state_dir / "agent-action.sock",
        "channel_id": "D1",
        "thread_ts": "1.0",
    }


def test_session_output_is_chunked_to_its_origin_thread_and_metered(monkeypatch, tmp_path):
    reset_fakes()
    install_fakes(monkeypatch, tmp_path)

    main_module.main()

    client = RecordingClient.instances[-1]
    runtime = RecordingRuntime.instances[-1]
    before = runtime.events.count("outbound")
    client.posts.clear()

    RecordingTransport.instances[-1].notifier("D-9", "9.1", "word " * 1000)

    assert len(client.posts) == 2
    assert {post["channel_id"] for post in client.posts} == {"D-9"}
    assert {post["thread_ts"] for post in client.posts} == {"9.1"}
    # Every chunk that reaches Slack must be metered, not just the first.
    assert runtime.events.count("outbound") == before + 2


def test_main_closes_servers_and_runtime_when_socket_source_fails(monkeypatch, tmp_path):
    reset_fakes()
    install_fakes(monkeypatch, tmp_path)
    RecordingSource.error = ConnectionError("socket failed")

    with pytest.raises(ConnectionError, match="socket failed"):
        main_module.main()

    assert RecordingActionServer.instances[-1].events[-1] == "close"
    assert RecordingApprovalServer.instances[-1].events[-1] == "close"
    assert RecordingRuntime.instances[-1].events[-1] == "close"


def test_main_rejects_second_daemon_owner_before_opening_clients(monkeypatch, tmp_path):
    reset_fakes()
    install_fakes(monkeypatch, tmp_path)
    RecordingRuntime.start_result = False

    with pytest.raises(RuntimeError, match="another Iris daemon already owns Socket Mode"):
        main_module.main()

    assert RecordingRuntime.instances[-1].events == ["start"]
    assert RecordingClient.instances == []
