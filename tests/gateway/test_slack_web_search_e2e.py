import json
from types import SimpleNamespace

from iris.agent_conversation import ClaudeToolAgentAdapter, GeneralAgentCoordinator
from iris.agent_runtime import AgentRuntime
from iris.slack import SlackGateway
from iris.tool_protocol import ToolRequest
from iris.tools.web import WebFetcher
from tests.gateway.test_slack_echo_e2e import dm_envelope
from tests.slack_fakes import RecordingSlackClient


def test_allowlisted_news_dm_reaches_production_search_and_replies_in_thread(monkeypatch, tmp_path):
    rss = (
        "<rss><channel><item><title>Latest Manila news</title>"
        "<link>https://news.example/manila</link></item></channel></rss>"
    )
    fetcher = WebFetcher()
    monkeypatch.setattr(fetcher, "fetch", lambda _arguments: {"text": rss})
    monkeypatch.setattr("iris.mcp_server.WebFetcher", lambda: fetcher)

    def run(command, **_kwargs):
        prompt = command[-1]
        if "Tool results so far: (none)" in prompt:
            result = ToolRequest(
                "news-1", "web_search", {"query": "latest news in Manila"}
            ).to_json()
        else:
            assert "Latest Manila news" in prompt
            assert "https://news.example/manila" in prompt
            result = "Latest Manila news: https://news.example/manila"
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": result}))

    conversation = GeneralAgentCoordinator(
        AgentRuntime({}),
        lambda message, turns, context: ClaudeToolAgentAdapter(
            tmp_path,
            tmp_path / "senses.json",
            turns,
            context,
            channel_id=message.channel_id,
            thread_ts=message.reply_thread_ts,
            run=run,
        ),
    )
    client = RecordingSlackClient()

    SlackGateway(["U-allowed"], client, handler=conversation.reply).handle_envelope(
        dm_envelope(text="What is the latest news in Manila?", ts="10.2", thread_ts="10.1")
    )

    assert client.messages == [{
        "channel_id": "D-1",
        "thread_ts": "10.1",
        "text": "Latest Manila news: https://news.example/manila",
    }]
