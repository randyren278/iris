from iris.capability_runtime import CapabilityBroker, CapabilityMode, CapabilityResult, RegisteredCapability
from iris.conversation import ConversationCoordinator
from iris.slack import SlackGateway
from iris.weather import weather_request
from tests.slack_fakes import RecordingSlackClient


def test_allowlisted_weather_dm_replies_in_its_thread():
    broker = CapabilityBroker({"weather": RegisteredCapability(
        CapabilityMode.READ_ONLY, lambda _request: CapabilityResult("Manila: 29°C, clear.", "Open-Meteo", "2026-08-19T10:00"))})
    conversation = ConversationCoordinator(None, capability_broker=broker, capability_selector=weather_request)
    client = RecordingSlackClient()
    envelope = {"type": "events_api", "event_id": "Ev-weather", "event": {"type": "message", "user": "U-allowed",
                "channel": "D-1", "text": "weather in Manila", "ts": "10.2", "thread_ts": "10.1", "channel_type": "im"}}
    SlackGateway(["U-allowed"], client, handler=conversation.reply).handle_envelope(envelope)
    assert client.messages == [{"channel_id": "D-1", "thread_ts": "10.1",
                                "text": "Manila: 29°C, clear.\n_Open-Meteo; observed 2026-08-19T10:00_"}]
