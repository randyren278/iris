from iris.launcher import Launcher


class Process:
    pid = 42


def test_claude_uses_manual_permission_mode_and_scrubs_claude_environment(tmp_path):
    calls = []
    launcher = Launcher(
        popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process(),
        environ={"PATH": "x", "CLAUDECODE": "nested", "CLAUDE_OTHER": "nested"},
    )

    launcher.launch("claude", cwd=tmp_path, prompt="fix tests")

    assert calls[0][0][0] == ["claude", "--permission-mode", "manual", "--remote-control", "fix tests"]
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
    assert command[0][:4] == ["claude", "--permission-mode", "manual", "--remote-control"]
    assert command[0][4] == "--settings"
    settings = __import__("json").loads(command[0][5])
    assert settings["hooks"]["PreToolUse"][0]["matcher"] == "*"
    assert "/opt/iris/python -m iris.approval_hook" in settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert kwargs["env"]["IRIS_APPROVAL_SOCKET"] == str(tmp_path / "approval.sock")


def test_streaming_claude_uses_the_required_verbose_flag(tmp_path):
    calls = []
    launcher = Launcher(
        popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process(),
        streaming=True,
    )

    launcher.launch("claude", cwd=tmp_path, prompt="inspect tests")

    command = calls[0][0][0]
    assert command[:8] == [
        "claude", "--permission-mode", "manual", "--input-format", "stream-json",
        "--output-format", "stream-json", "--include-partial-messages",
    ]
    assert "--print" in command
    assert "--verbose" in command
    assert "inspect tests" not in command
