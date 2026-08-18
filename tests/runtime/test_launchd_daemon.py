from pathlib import Path


def test_installer_bootstraps_a_throttled_observable_launch_agent():
    source = Path("scripts/install.sh").read_text()
    assert 'launchctl bootstrap "$domain" "$target"' in source
    assert 'launchctl kickstart -k "$domain/$label"' in source
    assert "for attempt in 1 2 3 4 5" in source
    assert "<key>ThrottleInterval</key><integer>10</integer>" in source
    assert "<key>StandardErrorPath</key>" in source
