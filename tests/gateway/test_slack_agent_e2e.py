from iris.agent_conversation import GeneralAgentCoordinator
from iris.agent_runtime import AgentReply, AgentRuntime
from iris.slack import SlackGateway
from iris.tool_protocol import ToolRequest
from tests.gateway.test_slack_echo_e2e import dm_envelope
from tests.slack_fakes import RecordingSlackClient


class Agent:
    def next_step(self, _text, results):
        if not results:
            return ToolRequest("one", "research", {"topic": "Iris"})
        return AgentReply(f"Found: {results[0].content['title']}")

    def handlers(self):
        return {"research": lambda arguments: {"title": arguments["topic"]}}


def test_allowlisted_dm_can_receive_agent_selected_read_only_tool_answer_in_same_thread():
    conversation = GeneralAgentCoordinator(AgentRuntime({}), lambda *_args: Agent())
    client = RecordingSlackClient()
    SlackGateway(["U-allowed"], client, handler=conversation.reply).handle_envelope(
        dm_envelope(text="research Iris", ts="10.2", thread_ts="10.1"))
    assert client.messages == [{"channel_id": "D-1", "thread_ts": "10.1", "text": "Found: Iris"}]
