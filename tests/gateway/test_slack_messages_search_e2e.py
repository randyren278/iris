import json
from types import SimpleNamespace

from iris.agent_conversation import ClaudeToolAgentAdapter, GeneralAgentCoordinator
from iris.agent_runtime import AgentRuntime
from iris.slack import SlackGateway
from iris.tool_protocol import ToolRequest
from tests.gateway.test_slack_echo_e2e import dm_envelope
from tests.slack_fakes import RecordingSlackClient


def test_allowlisted_dm_reaches_production_messages_search_and_replies_in_thread(monkeypatch, tmp_path):
    class Messages:
        def __init__(self, path):
            assert path == tmp_path / "chat.db"

        def search(self, arguments):
            assert arguments == {"query": "Lauren Kate Yu"}
            return {"query": arguments["query"], "matches": [{
                "conversation": "Lauren Kate Yu",
                "direction": "received",
                "sent_at": "2026-08-01T10:00:00+00:00",
                "text": "Dinner on Friday",
            }]}

    monkeypatch.setattr("iris.mcp_server.MessagesSearch", Messages)
    turns = []

    def run(command, **_kwargs):
        prompt = command[-1]
        turns.append(prompt)
        if "Search my iMessage logs" not in prompt:
            result = "I don't know who Lauren Kate Yu is yet."
        elif "Tool results so far: (none)" in prompt:
            assert "Who is Lauren Kate Yu" in prompt
            result = ToolRequest(
                "messages-1", "messages_search", {"query": "Lauren Kate Yu"}
            ).to_json()
        else:
            assert "Dinner on Friday" in prompt
            assert '"trust":"untrusted_data"' not in prompt
            result = "I found a conversation with Lauren Kate Yu mentioning dinner on Friday."
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": result}))

    conversation = GeneralAgentCoordinator(
        AgentRuntime({}),
        lambda message, history, context: ClaudeToolAgentAdapter(
            tmp_path,
            tmp_path / "senses.json",
            history,
            context,
            messages_path=tmp_path / "chat.db",
            channel_id=message.channel_id,
            thread_ts=message.reply_thread_ts,
            run=run,
        ),
    )
    client = RecordingSlackClient()

    gateway = SlackGateway(["U-allowed"], client, handler=conversation.reply)
    gateway.handle_envelope(
        dm_envelope(text="Who is Lauren Kate Yu?", ts="10.1", thread_ts="10.1")
    )
    gateway.handle_envelope(
        dm_envelope(
            event_id="Ev-2", text="Search my iMessage logs", ts="10.2", thread_ts="10.1"
        )
    )

    assert len(turns) == 3
    assert client.messages == [
        {
            "channel_id": "D-1",
            "thread_ts": "10.1",
            "text": "I don't know who Lauren Kate Yu is yet.",
        },
        {
            "channel_id": "D-1",
            "thread_ts": "10.1",
            "text": "I found a conversation with Lauren Kate Yu mentioning dinner on Friday.",
        },
    ]
