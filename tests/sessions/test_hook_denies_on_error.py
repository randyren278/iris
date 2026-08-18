"""The hook entry point must deny, not allow, on every failure path."""
import io
import json
import sys

from iris import approval_hook


def test_hook_denies_when_socket_env_is_missing(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_name": "Bash"})))
    monkeypatch.delenv("IRIS_APPROVAL_SOCKET", raising=False)

    assert approval_hook.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_denies_on_malformed_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    monkeypatch.setenv("IRIS_APPROVAL_SOCKET", "/tmp/does-not-matter.sock")

    assert approval_hook.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_denies_on_non_dict_stdin(monkeypatch, capsys):
    """Valid JSON that isn't an object must still deny, not crash with AttributeError."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps([1, 2, 3])))
    monkeypatch.setenv("IRIS_APPROVAL_SOCKET", "/tmp/does-not-matter.sock")

    assert approval_hook.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
