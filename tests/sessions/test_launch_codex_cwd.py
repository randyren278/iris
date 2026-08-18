from iris.launcher import CODEX_SANDBOX, Launcher


class Process:
    pid = 43


def codex_command(tmp_path):
    calls = []
    launcher = Launcher(popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process())
    launcher.launch("codex", cwd=tmp_path, prompt="write docs")
    return calls[0]


def test_codex_launch_uses_selected_project_as_cwd(tmp_path):
    args, kwargs = codex_command(tmp_path)
    assert args[0][-1] == "write docs"
    assert kwargs["cwd"] == str(tmp_path.resolve())


def test_codex_runs_headless_not_the_interactive_cli(tmp_path):
    """The bare `codex <prompt>` form is the interactive CLI and exits with
    "stdin is not a terminal" under launchd, where Iris launches it."""
    command = codex_command(tmp_path)[0][0]
    assert command[:2] == ["codex", "exec"]


def test_codex_is_confined_to_the_workspace(tmp_path):
    """Iris cannot mediate Codex tool calls, so the sandbox is the boundary.
    Passing it on the command line overrides sandbox_mode in the operator's
    ~/.codex/config.toml, which may be danger-full-access."""
    command = codex_command(tmp_path)[0][0]
    assert command[command.index("--sandbox") + 1] == CODEX_SANDBOX == "workspace-write"


def test_codex_never_bypasses_its_own_guardrails(tmp_path):
    command = codex_command(tmp_path)[0][0]
    assert not any(flag.startswith("--dangerously-bypass") for flag in command)


def test_codex_model_stays_unpinned(tmp_path):
    """The model comes from ~/.codex/config.toml so it lives in one place.
    --ignore-user-config would neutralize the sandbox setting but discard the
    model with it, so it is deliberately not used."""
    command = codex_command(tmp_path)[0][0]
    assert "--model" not in command and "-m" not in command
    assert "--ignore-user-config" not in command
