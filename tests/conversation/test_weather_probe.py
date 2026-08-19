from iris.capability_runtime import CapabilityError, CapabilityRequest, CapabilityResult
from iris.weather_probe import main, probe


def test_probe_prints_provider_metadata_only():
    def service(request):
        assert request == CapabilityRequest("weather", {"location": "Manila"})
        return CapabilityResult("Manila: 29°C, clear.", "Weather data by Open-Meteo.com", "2026-08-19T10:00")

    output = probe(service)

    assert output == "Weather provider reachable: Weather data by Open-Meteo.com; observed 2026-08-19T10:00."
    assert "29°C" not in output


def test_probe_reports_a_safe_failure(monkeypatch, capsys):
    monkeypatch.setattr("iris.weather_probe.probe", lambda: (_ for _ in ()).throw(CapabilityError("unavailable")))

    assert main() == 1
    assert capsys.readouterr().out == "Weather provider probe failed: unavailable\n"
