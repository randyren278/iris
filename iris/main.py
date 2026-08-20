"""Production Slack daemon plus the retained experimental iMessage gateway."""
import logging

from iris.allowlist import Allowlist
from iris.config import load
from iris.grammar import parse
from iris.poller import Poller

LOG = logging.getLogger(__name__)


def route_message(message, router, conversation):
    """Keep explicit commands ahead of every conversational capability."""
    return router.handle(message) if parse(message.text) is not None else conversation.reply(message)


class Gateway:
    """Route inbound messages through the allowlist and reply to allowed ones."""
    def __init__(self, config, *, poller=None):
        self.config = config
        self.allowlist = Allowlist.from_config(config)
        self.poller = poller or Poller(
            config.chatdb, config.state_path,
            self_chat_guid=config.self_chat_guid,
            self_command_suffix=config.self_command_suffix,
        )

    def handle(self, message):
        if not message.is_self_chat and not self.allowlist.allows(message.handle):
            # Do not include a stranger's body in this early operational log.
            LOG.warning("ignored message from non-allowlisted handle")
            return False
        sent = self.config.sender(message.chat_guid, message.body)
        if sent:
            self.poller.track_echo(message.chat_guid, message.body)
        return sent

    def run_once(self):
        return [self.handle(message) for message in self.poller.poll_once()]

    def run_forever(self, stop=None):
        self.poller.run(self.handle, stop=stop)


def main():
    logging.basicConfig(level=logging.INFO)
    # iMessage remains an experiment; the production daemon is Slack Socket
    # Mode and therefore has no inbound HTTP listener.
    from iris.slack import SlackGateway, SlackWebClient, SocketModeEventSource
    from iris.slack_config import load_credentials
    from iris.audit import AuditLog
    from iris.approvals import ApprovalQueue, ApprovalServer
    from iris.agent_actions import AgentActionServer
    from iris.launcher import Launcher
    from iris.projects import ProjectCatalog
    from iris.registry import SessionRegistry
    from iris.router import CommandRouter
    from iris.sessions import SessionController
    from iris.doctor import ensure_private_state_dir
    from iris.runtime import RuntimeSupervisor
    from iris.conversation import MemoryContext
    from iris.agent_conversation import ClaudeMCPAgentAdapter, GeneralAgentCoordinator
    from iris.agent_runtime import AgentRuntime
    from iris.memory import MemoryStore
    from iris.session_transport import SessionTransport
    from iris.output import split_for_slack

    config = load()
    credentials = load_credentials()
    state_dir = ensure_private_state_dir("~/.iris")
    runtime = RuntimeSupervisor(state_dir)
    if not runtime.start():
        raise RuntimeError("another Iris daemon already owns Socket Mode")
    runtime.start_heartbeat()
    client = SlackWebClient(credentials.bot_token)

    def notify_session(channel_id, thread_ts, text):
        for chunk in split_for_slack(text):
            client.post_message(channel_id=channel_id, thread_ts=thread_ts, text=chunk)
            runtime.outbound()

    transport = SessionTransport(notify_session)

    def reject_unbound_approval(_text):
        raise RuntimeError("approval request has no Slack origin")

    def notifier_for_approval(channel_id, thread_ts):
        def notify(text):
            for chunk in split_for_slack(text):
                client.post_message(channel_id=channel_id, thread_ts=thread_ts, text=chunk)
                runtime.outbound()
        return notify

    approvals = ApprovalQueue(notifier=reject_unbound_approval)
    approval_server = ApprovalServer(
        state_dir / "approval.sock",
        approvals,
        notifier_for_context=notifier_for_approval,
    )
    approval_server.start()

    projects = ProjectCatalog.discover(config.projects_root)
    sessions = SessionController(
        SessionRegistry(state_dir / "sessions.json"),
        Launcher(approval_socket=approval_server.path, streaming=True),
        transport=transport,
        disarm_path=state_dir / "disarmed",
    )
    memory = MemoryStore(state_dir / "memory.json")
    router = CommandRouter(projects, sessions, approvals, memory=memory)

    action_server = AgentActionServer(
        state_dir / "agent-action.sock",
        approvals,
        projects,
        sessions,
        notifier_for_context=notifier_for_approval,
    )
    action_server.start()

    def memory_context(_key, query):
        return tuple(MemoryContext(item.claim, item.trust, item.source_ref)
                     for item in memory.retrieve(query))

    conversation = GeneralAgentCoordinator(
        AgentRuntime({}),
        lambda message, turns, context: ClaudeMCPAgentAdapter(
            config.projects_root,
            state_dir / "senses.json",
            turns,
            context,
            action_socket=action_server.path,
            channel_id=message.channel_id,
            thread_ts=message.reply_thread_ts,
        ),
        context_provider=memory_context,
    )

    gateway = SlackGateway(
        config.slack_allowlist,
        client,
        handler=lambda message: route_message(message, router, conversation),
        audit=AuditLog(state_dir / "audit.jsonl"),
        on_inbound=runtime.inbound,
        on_outbound=runtime.outbound,
    )
    source = SocketModeEventSource(credentials)
    try:
        source.run(gateway.handle_envelope, on_connected=runtime.connected,
                   on_disconnected=runtime.disconnected)
    finally:
        action_server.close()
        approval_server.close()
        runtime.close()


if __name__ == "__main__":  # pragma: no cover - process entry point
    main()
