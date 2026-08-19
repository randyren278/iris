"""Operator-run, credential-free reachability probe for the weather provider."""
from __future__ import annotations

from iris.capability_runtime import CapabilityError, CapabilityRequest
from iris.weather import WeatherService


def probe(service=None) -> str:
    result = (service or WeatherService())(CapabilityRequest("weather", {"location": "Manila"}))
    return f"Weather provider reachable: {result.source}; observed {result.observed_at}."


def main() -> int:
    try:
        print(probe())
    except CapabilityError as error:
        print(f"Weather provider probe failed: {error}")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
