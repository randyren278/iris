"""Bounded, read-only current-weather capability backed by Open-Meteo."""
from __future__ import annotations

import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from iris.capability_runtime import CapabilityError, CapabilityRequest, CapabilityResult

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 8
SOURCE = "Weather data by Open-Meteo.com"

_WEATHER = re.compile(r"\bweather\b", re.IGNORECASE)
_LOCATION = re.compile(r"\b(?:in|for|at)\s+([\w .,'-]+?)(?:\?|$)", re.IGNORECASE)
_CODES = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "rime fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
    81: "heavy rain showers", 82: "violent rain showers", 95: "thunderstorms",
}


def weather_request(text: str) -> CapabilityRequest | None:
    """Recognize an explicit weather question without treating it as a command."""
    if not _WEATHER.search(text):
        return None
    match = _LOCATION.search(text)
    if match is None or not match.group(1).strip():
        return CapabilityRequest("weather", {})
    return CapabilityRequest("weather", {"location": match.group(1).strip(" .,?!")})


class WeatherService:
    def __init__(self, *, opener=urlopen, timeout=TIMEOUT_SECONDS):
        self._opener = opener
        self._timeout = timeout

    def __call__(self, request: CapabilityRequest) -> CapabilityResult:
        location = request.arguments.get("location", "").strip()
        if not location:
            raise CapabilityError("Tell me the city, for example: `what's the weather in Manila?`")
        place = self._json(GEOCODING_URL, {"name": location, "count": "1", "language": "en", "format": "json"})
        results = place.get("results") if isinstance(place, dict) else None
        if not isinstance(results, list) or not results or not isinstance(results[0], dict):
            raise CapabilityError(f"I couldn't find a weather location for {location!r}.")
        match = results[0]
        latitude, longitude = match.get("latitude"), match.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise CapabilityError("The weather provider returned an invalid location.")
        forecast = self._json(FORECAST_URL, {
            "latitude": str(latitude), "longitude": str(longitude), "current":
            "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "timezone": "auto",
        })
        current = forecast.get("current") if isinstance(forecast, dict) else None
        if not isinstance(current, dict) or not all(key in current for key in ("temperature_2m", "weather_code", "time")):
            raise CapabilityError("The weather provider returned incomplete current conditions.")
        name = ", ".join(str(value) for value in (match.get("name"), match.get("country")) if value)
        condition = _CODES.get(current["weather_code"], "unknown conditions")
        feels = current.get("apparent_temperature")
        feel_text = f", feels like {feels}°C" if isinstance(feels, (int, float)) else ""
        wind = current.get("wind_speed_10m")
        wind_text = f", wind {wind} km/h" if isinstance(wind, (int, float)) else ""
        return CapabilityResult(
            text=f"{name}: {current['temperature_2m']}°C, {condition}{feel_text}{wind_text}.",
            source=SOURCE,
            # The provider's current-condition timestamp is Iris's freshness
            # indicator; it is surfaced in every Slack reply.
            observed_at=str(current["time"]),
        )

    def _json(self, endpoint: str, parameters: dict[str, str]) -> dict:
        request = Request(f"{endpoint}?{urlencode(parameters)}", headers={"User-Agent": "Iris/0.1 weather"})
        try:
            with self._opener(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError):
            raise CapabilityError("I couldn't get live weather right now. Please try again shortly.") from None
        return payload if isinstance(payload, dict) else {}
