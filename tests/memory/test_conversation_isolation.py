"""A nested claude process must not inherit operator settings.

Without isolation, every Iris DM runs the operator's hooks: raw transcripts get
distilled and written wherever those hooks point, unrelated context is injected
into Iris's prompt, and each turn costs extra model calls. The retained text
backend is tool-less; the production general agent uses only Iris's explicit MCP
catalog. These tests keep the surrounding Claude process boundary intact.
"""
import ast
import pathlib

import pytest

from iris.conversation import CLAUDE_ISOLATION, CONVERSATION_MODEL, ClaudeTextBackend
from iris.launcher import CODING_MODEL, Launcher

IRIS = pathlib.Path(__file__).resolve().parents[2] / "iris"


def flag_value(command, flag):
    return command[command.index(flag) + 1]


def conversation_command():
    captured = {}

    def run(command, **kwargs):
        captured["command"] = command
        raise FileNotFoundError  # short-circuit; the reply is not under test

    ClaudeTextBackend(run=run).reply((), ())
    return captured["command"]


def launcher_command(tmp_path, *, streaming, approval_socket=None):
    captured = {}

    def popen(command, **kwargs):
        captured["command"] = command
        return object()

    Launcher(popen=popen, streaming=streaming, approval_socket=approval_socket).launch(
        "claude", cwd=tmp_path, prompt="do the thing")
    return captured["command"]


def test_conversation_turn_loads_no_settings_files():
    command = conversation_command()
    assert flag_value(command, "--setting-sources") == ""
    assert "--strict-mcp-config" in command


def test_conversation_turn_runs_on_the_pinned_model():
    assert flag_value(conversation_command(), "--model") == CONVERSATION_MODEL
    assert CONVERSATION_MODEL == "sonnet"


def test_conversation_turn_still_has_no_tools():
    """The retained text backend remains intentionally tool-less."""
    assert flag_value(conversation_command(), "--tools") == ""
    assert flag_value(conversation_command(), "--permission-mode") == "manual"


@pytest.mark.parametrize("streaming", [False, True])
def test_coding_session_is_isolated_and_pinned(tmp_path, streaming):
    command = launcher_command(tmp_path, streaming=streaming)
    assert flag_value(command, "--setting-sources") == ""
    assert "--strict-mcp-config" in command
    assert flag_value(command, "--model") == CODING_MODEL == "opus"
    assert flag_value(command, "--permission-mode") == "manual"


@pytest.mark.parametrize("streaming", [False, True])
def test_isolation_does_not_displace_the_approval_hook(tmp_path, streaming):
    """--setting-sources "" suppresses settings *files*; the explicit --settings
    JSON carrying Iris's PreToolUse hook must survive alongside it. iris.hook_probe
    verifies this against the real CLI; this pins the command we rely on."""
    command = launcher_command(tmp_path, streaming=streaming, approval_socket="/tmp/approval.sock")
    assert "--settings" in command
    assert "PreToolUse" in flag_value(command, "--settings")
    assert flag_value(command, "--setting-sources") == ""


def test_bare_flag_is_never_used():
    """--bare skips keychain reads and authenticates only via an API key, so it
    breaks a subscription login. Matches the quoted argument, not prose about it."""
    for source in IRIS.rglob("*.py"):
        assert '"--bare"' not in source.read_text(), source


def test_isolation_guard_covers_every_claude_command_literal():
    """Every source-level Claude argv literal containing CLI flags is isolated.

    Use Python's AST instead of a raw text regex so data schemas such as
    ``{"enum": ["claude", "codex"]}`` are not mistaken for subprocess argv.
    A candidate must be a list whose first element is the executable name and
    which also contains at least one CLI flag string.
    """
    offenders = []
    for source in IRIS.rglob("*.py"):
        tree = ast.parse(source.read_text(), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.List) or not node.elts:
                continue
            first = node.elts[0]
            if not isinstance(first, ast.Constant) or first.value != "claude":
                continue
            literal_strings = [item.value for item in node.elts
                               if isinstance(item, ast.Constant) and isinstance(item.value, str)]
            if not any(value.startswith("--") for value in literal_strings):
                continue
            rendered = ast.unparse(node)
            if "CLAUDE_ISOLATION" not in rendered and "--setting-sources" not in rendered:
                offenders.append(f"{source.name}:{node.lineno}")
    assert not offenders, f"un-isolated claude invocation(s): {offenders}"


def test_isolation_constant_is_the_single_source():
    assert CLAUDE_ISOLATION == ["--setting-sources", "", "--strict-mcp-config",
                                "--disable-slash-commands"]
