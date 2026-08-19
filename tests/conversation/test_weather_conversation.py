import json
from types import SimpleNamespace

from iris.capability_runtime import CapabilityBroker, CapabilityMode, RegisteredCapability
from iris.conversation import ConversationCoordinator
from iris.weather import SOURCE, WeatherService, weather_request


class Response:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self): return json.dumps(self.payload).encode()


def opener(request, *, timeout):
    if "geocoding" in request.full_url:
        return Response({"results": [{"name": "Manila", "country": "Philippines", "latitude": 14.6, "longitude": 121.0}]})
    return Response({"current": {"temperature_2m": 29.0, "apparent_temperature": 33.0, "weather_code": 2,
                                   "wind_speed_10m": 11.0, "time": "2026-08-19T10:00"}})


class Backend:
    def reply(self, *_args): raise AssertionError("weather must not reach the model backend")


def coordinator():
    broker = CapabilityBroker({"weather": RegisteredCapability(CapabilityMode.READ_ONLY, WeatherService(opener=opener))})
    return ConversationCoordinator(Backend(), capability_broker=broker, capability_selector=weather_request)


def test_weather_question_returns_attributed_current_conditions():
    message = SimpleNamespace(channel_id="D", reply_thread_ts="T", text="what's the weather in Manila?")
    reply = coordinator().reply(message)
    assert "Manila, Philippines: 29.0°C, partly cloudy" in reply
    assert SOURCE in reply and "2026-08-19T10:00" in reply


def test_weather_without_location_asks_for_a_city_without_calling_model():
    message = SimpleNamespace(channel_id="D", reply_thread_ts="T", text="what's the weather rn iris")
    assert "Tell me the city" in coordinator().reply(message)


def test_non_weather_conversation_keeps_existing_backend_path():
    class TextBackend:
        def reply(self, *_args): return "normal reply"
    result = ConversationCoordinator(TextBackend(), capability_selector=weather_request).reply(
        SimpleNamespace(channel_id="D", reply_thread_ts="T", text="hello"))
    assert result == "normal reply"
