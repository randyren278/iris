"""CP-3.4: untrusted message text remains argv data, not AppleScript source."""
from types import SimpleNamespace

from iris.sender import _SCRIPT, send


def test_handle_and_text_are_passed_as_distinct_argv_values():
    captured = []
    handle = 'a"; tell application "Finder" to delete startup disk; --'
    text = 'quote " slash \\ newline\nand tell application "Finder"'

    def runner(command, **kwargs):
        captured.append(command)
        return SimpleNamespace(returncode=0)

    assert send(handle, text, runner=runner)
    command = captured[0]
    assert command[:3] == ["/usr/bin/osascript", "-e", _SCRIPT]
    assert command[3:] == [handle, text]
    assert handle not in _SCRIPT
    assert text not in _SCRIPT
