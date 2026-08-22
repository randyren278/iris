import json

from iris.launcher import CODING_MODEL, Launcher


class Process:
    pid = 42


def flag_value(command, flag):
    return command[command.index(flag) + 1]


def test_claude_uses_manual_permission_mode_and_scrubs_claude_environment(tmp_path):
    calls = []
    launcher = Launcher(
        popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process(),
        environ={"PATH": "x", "CLAUDECODE": "nested", "CLAUDE_OTHER": "nested"},
    )

    launcher.launch("claude", cwd=tmp_path, prompt="fix tests")

    command = calls[0][0][0]
    assert command[0] == "claude"
    assert flag_value(command, "--permission-mode") == "manual"
    assert flag_value(command, "--model") == CODING_MODEL
    assert "--remote-control" in command
    assert command[-1] == "fix tests"
    assert calls[0][1]["env"] == {"PATH": "x"}


def test_claude_approval_hook_uses_the_private_local_socket(tmp_path):
    calls = []
    launcher = Launcher(
        popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process(),
        environ={"PATH": "x"}, approval_socket=tmp_path / "approval.sock",
        hook_python="/opt/iris/python",
    )

    launcher.launch("claude", cwd=tmp_path, prompt="fix tests")

    command, kwargs = calls[0]
    assert command[0][0] == "claude"
    assert flag_value(command[0], "--permission-mode") == "manual"
    assert "--remote-control" in command[0]
    settings = json.loads(flag_value(command[0], "--settings"))
    assert settings["hooks"]["PreToolUse"][0]["matcher"] == "*"
    assert "/opt/iris/python -m iris.approval_hook" in settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert kwargs["env"]["IRIS_APPROVAL_SOCKET"] == str(tmp_path / "approval.sock")


def test_claude_approval_hook_receives_exact_slack_origin(tmp_path):
    calls = []
    launcher = Launcher(
        popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process(),
        environ={"PATH": "x"}, approval_socket=tmp_path / "approval.sock",
    )

    launcher.launch(
        "claude",
        cwd=tmp_path,
        prompt="fix tests",
        approval_context=("D-origin", "42.1"),
    )

    environment = calls[0][1]["env"]
    assert environment["IRIS_APPROVAL_CHANNEL_ID"] == "D-origin"
    assert environment["IRIS_APPROVAL_THREAD_TS"] == "42.1"


def test_streaming_claude_uses_the_required_verbose_flag(tmp_path):
    calls = []
    launcher = Launcher(
        popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process(),
        streaming=True,
    )

    launcher.launch("claude", cwd=tmp_path, prompt="inspect tests")

    command = calls[0][0][0]
    assert command[0] == "claude"
    assert flag_value(command, "--permission-mode") == "manual"
    assert flag_value(command, "--input-format") == "stream-json"
    assert flag_value(command, "--output-format") == "stream-json"
    assert "--include-partial-messages" in command
    assert "--print" in command
    assert "--verbose" in command
    # A streaming session receives its prompt over stdin, never on argv.
    assert "inspect tests" not in command


def test_autonomous_claude_bypasses_permissions_and_installs_no_tool_approval_hook(tmp_path):
    calls = []
    launcher = Launcher(
        popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process(),
        environ={"PATH": "x"}, approval_socket=tmp_path / "approval.sock",
        streaming=True, autonomous=True,
    )

    launcher.launch("claude", cwd=tmp_path, prompt="fix tests",
                    approval_context=("D-origin", "42.1"))

    command = calls[0][0][0]
    assert flag_value(command, "--permission-mode") == "bypassPermissions"
    # An approved session runs its own tool calls: no PreToolUse hook is wired.
    assert "--settings" not in command
    # Isolation from the operator's own settings is not part of the trade.
    assert flag_value(command, "--setting-sources") == ""
    assert "--strict-mcp-config" in command


def test_autonomy_is_opt_in_so_the_default_launcher_still_gates_every_tool_call(tmp_path):
    calls = []
    launcher = Launcher(
        popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process(),
        environ={"PATH": "x"}, approval_socket=tmp_path / "approval.sock",
    )

    launcher.launch("claude", cwd=tmp_path, prompt="fix tests")

    command = calls[0][0][0]
    assert flag_value(command, "--permission-mode") == "manual"
    assert json.loads(flag_value(command, "--settings"))["hooks"]["PreToolUse"]
