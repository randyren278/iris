"""A Slack-derived prompt must never be parsable as a CLI flag by the
downstream `claude`/`codex` binaries.

Both use argument parsers (commander.js, clap) that treat a trailing
positional matching a real flag name as that flag, not literal text, unless a
`--` end-of-options marker precedes it. Confirmed live against the real
binaries: `claude ... -- --version` runs a turn with prompt text "--version"
sent to the API (an error, since the model name was invalid), while the same
command without `--` prints the version and exits immediately without ever
reaching argument construction for a turn. Same pattern for
`codex exec ... -- --help` (hangs waiting on a real turn) vs. without `--`
(prints help and exits 0). Without the marker, a prompt of exactly
`--dangerously-skip-permissions` or `--dangerously-bypass-approvals-and-sandbox`
would very plausibly disable permission checks / sandbox confinement.
"""
from iris.launcher import Launcher


class Process:
    pid = 44


def launched_command(tool, prompt, tmp_path):
    calls = []
    launcher = Launcher(popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process())
    launcher.launch(tool, cwd=tmp_path, prompt=prompt)
    return calls[0][0][0]


def test_claude_prompt_cannot_be_parsed_as_a_flag(tmp_path):
    command = launched_command("claude", "--dangerously-skip-permissions", tmp_path)
    assert command[-1] == "--dangerously-skip-permissions"
    assert command[-2] == "--"


def test_codex_prompt_cannot_be_parsed_as_a_flag(tmp_path):
    command = launched_command("codex", "--dangerously-bypass-approvals-and-sandbox", tmp_path)
    assert command[-1] == "--dangerously-bypass-approvals-and-sandbox"
    assert command[-2] == "--"
