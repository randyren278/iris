"""The menu bar indicator must be a correct verdict on the daemon.

Every state is exercised against a fixture state directory via IRIS_STATE_DIR,
so these tests need no daemon, no launchd, and no SwiftBar.
"""
import inspect
import json
import os
import pathlib
import re
import shutil
import subprocess
import time

import pytest

from iris.runtime import StatusStore

REPO = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = REPO / "scripts" / "menubar" / "iris.30s.sh"
# Above macOS pid_max (99998), so kill -0 can never find it.
DEAD_PID = 4_000_000


def render(state_dir, *, path=None):
    environment = dict(os.environ, IRIS_STATE_DIR=str(state_dir))
    if path is not None:
        environment["PATH"] = path
    result = subprocess.run(["/bin/bash", str(PLUGIN)], capture_output=True, text=True,
                            env=environment)
    assert result.returncode == 0, result.stderr
    return result.stdout


def write_status(state_dir, **overrides):
    state_dir.mkdir(parents=True, exist_ok=True)
    status = {"pid": os.getpid(), "boot_id": "cccf9c4c5607406694f8868b87d58e85",
              "state": "online", "updated_at": time.time(), "last_inbound_at": None,
              "last_outbound_at": None, "last_error": None}
    status.update(overrides)
    (state_dir / "runtime.json").write_text(json.dumps(status))


def color(output):
    heading = output.splitlines()[0]
    assert "color=" in heading, heading
    return heading.split("color=")[1].strip()


def test_no_runtime_record_is_gray(tmp_path):
    output = render(tmp_path)
    assert color(output) == "gray"
    assert "no runtime record" in output


def test_no_runtime_record_still_surfaces_persistent_disarm(tmp_path):
    (tmp_path / "disarmed").write_text("disarmed\n")
    output = render(tmp_path)
    assert color(output) == "gray"
    assert "Control: DISARMED" in output


def test_corrupt_runtime_record_is_orange_not_a_verdict(tmp_path):
    (tmp_path / "runtime.json").write_text("{not json")
    output = render(tmp_path)
    assert color(output) == "orange"
    assert "unreadable" in output


def test_nonpositive_pid_is_not_treated_as_a_live_daemon(tmp_path):
    write_status(tmp_path, pid=0)
    output = render(tmp_path)
    assert color(output) == "orange"
    assert "unreadable" in output


def test_online_and_fresh_is_green(tmp_path):
    write_status(tmp_path)
    output = render(tmp_path)
    assert color(output) == "green"
    assert "Online" in output
    assert "Control: armed" in output


def test_online_but_disarmed_is_orange_and_explicit(tmp_path):
    write_status(tmp_path)
    (tmp_path / "disarmed").write_text("disarmed\n")
    output = render(tmp_path)
    assert color(output) == "orange"
    assert "Online" in output
    assert "Control: DISARMED — re-arm from Terminal" in output
    assert "rearm" not in output.lower().split("Restart Iris", 1)[1]


def test_offline_is_red(tmp_path):
    write_status(tmp_path, state="offline")
    assert color(render(tmp_path)) == "red"


def test_offline_remains_red_when_also_disarmed(tmp_path):
    write_status(tmp_path, state="offline")
    (tmp_path / "disarmed").write_text("disarmed\n")
    output = render(tmp_path)
    assert color(output) == "red"
    assert "Control: DISARMED" in output


def test_starting_is_orange(tmp_path):
    write_status(tmp_path, state="starting")
    output = render(tmp_path)
    assert color(output) == "orange"
    assert "Starting" in output


def test_stale_heartbeat_is_orange_even_though_state_says_online(tmp_path):
    write_status(tmp_path, updated_at=time.time() - 600)
    output = render(tmp_path)
    assert color(output) == "orange"
    assert "Stale" in output


def test_fresh_record_for_a_dead_process_is_red_immediately(tmp_path):
    """A SIGKILLed daemon leaves state "online" behind; freshness alone would
    keep the icon green for a full staleness window over a dead process."""
    write_status(tmp_path, pid=DEAD_PID)
    output = render(tmp_path)
    assert color(output) == "red"
    assert "is gone" in output


def test_green_boundary_matches_the_staleness_threshold(tmp_path):
    write_status(tmp_path, updated_at=time.time() - 5)
    assert color(render(tmp_path)) == "green"
    write_status(tmp_path, updated_at=time.time() - 95)
    assert color(render(tmp_path)) == "orange"


def test_staleness_threshold_matches_the_runtime_default():
    """Drift here would make the icon and `irisctl verify-online` disagree."""
    default = inspect.signature(StatusStore.healthy).parameters["max_age"].default
    assert f"STALE_AFTER_SECONDS={int(default)}" in PLUGIN.read_text()


def test_activity_ages_are_reported(tmp_path):
    write_status(tmp_path, last_inbound_at=time.time() - 180, last_outbound_at=time.time() - 120)
    output = render(tmp_path)
    assert "Last message in: 3m ago" in output
    assert "Last message out: 2m ago" in output


def test_absent_activity_reads_as_never_this_boot(tmp_path):
    write_status(tmp_path)
    output = render(tmp_path)
    assert "Last message in: never this boot" in output
    assert "Last message out: never this boot" in output


def test_last_error_surfaces_only_when_present(tmp_path):
    write_status(tmp_path)
    assert "Last error" not in render(tmp_path)
    write_status(tmp_path, state="offline", last_error="ConnectionResetError")
    assert "Last error: ConnectionResetError" in render(tmp_path)


def test_restart_action_targets_the_launchd_job(tmp_path):
    write_status(tmp_path)
    output = render(tmp_path)
    assert f"param3=gui/{os.getuid()}/com.iris.gateway" in output
    assert "param1=kickstart param2=-k" in output


def test_reads_no_conversation_or_credential_state():
    """The disarm marker is control-plane state; private conversation-derived
    records remain entirely outside the SwiftBar process."""
    source = PLUGIN.read_text()
    assert "disarmed" in source
    for private in ("sessions.json", "audit.jsonl", "memory.json", "config.toml", "senses.json"):
        assert private not in source


def fallback_path(tmp_path):
    tools = tmp_path / "bin"
    tools.mkdir()
    for tool in ("date", "id", "python3"):
        resolved = shutil.which(tool)
        assert resolved, f"{tool} is required to exercise the fallback"
        (tools / tool).symlink_to(resolved)
    assert shutil.which("jq", path=str(tools)) is None
    return str(tools)


def stable(output):
    return re.sub(r"\d+(?=[smhd] ago)", "N", output)


def test_python_fallback_renders_the_same_verdict_as_jq(tmp_path):
    """`jq` is not guaranteed on every macOS; the fallback must agree with it."""
    if shutil.which("jq") is None:
        pytest.skip("jq is absent, so there is no jq rendering to compare against")
    write_status(tmp_path, last_inbound_at=time.time() - 180, last_error="TimeoutError")
    assert stable(render(tmp_path, path=fallback_path(tmp_path))) == stable(render(tmp_path))


def test_python_fallback_handles_state_paths_with_quotes_and_spaces(tmp_path):
    state_dir = tmp_path / "state with ' quote"
    write_status(state_dir)
    output = render(state_dir, path=fallback_path(tmp_path))
    assert color(output) == "green"
    assert "Online" in output
