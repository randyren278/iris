import pytest

from iris.capability_runtime import (
    CapabilityBroker,
    CapabilityError,
    CapabilityMode,
    CapabilityRequest,
    CapabilityResult,
    RegisteredCapability,
)


def test_broker_returns_attributed_read_only_result():
    broker = CapabilityBroker({
        "weather": RegisteredCapability(
            CapabilityMode.READ_ONLY,
            lambda request: CapabilityResult(
                text=f"Weather for {request.arguments['location']}: clear.",
                source="Open-Meteo",
                observed_at="2026-08-19T10:00:00+08:00",
            ),
        )
    })

    result = broker.invoke(CapabilityRequest("weather", {"location": "Manila"}))

    assert result.source == "Open-Meteo"
    assert "Manila" in result.text


@pytest.mark.parametrize("mode", [CapabilityMode.PROPOSAL_ONLY, CapabilityMode.CONSEQUENTIAL])
def test_broker_rejects_non_read_only_capabilities(mode):
    called = []
    broker = CapabilityBroker({
        "write_file": RegisteredCapability(mode, lambda _request: called.append(True)),
    })

    with pytest.raises(CapabilityError, match="explicit Iris command"):
        broker.invoke(CapabilityRequest("write_file", {}))

    assert called == []


def test_broker_rejects_unknown_and_malformed_results():
    broker = CapabilityBroker({
        "broken": RegisteredCapability(CapabilityMode.READ_ONLY, lambda _request: None),
    })

    with pytest.raises(CapabilityError, match="not available"):
        broker.invoke(CapabilityRequest("unknown", {}))
    with pytest.raises(CapabilityError, match="invalid response"):
        broker.invoke(CapabilityRequest("broken", {}))
