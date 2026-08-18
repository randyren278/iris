import pytest

from iris.grammar import IndexedCommand, Simple, TextCommand, parse


@pytest.mark.parametrize(("text", "expected"), [
    ("ls", Simple("ls")), ("projects", Simple("projects")),
    ("sessions", Simple("sessions")), ("link", Simple("link")),
    ("memories", Simple("memories")),
    ("y", Simple("y")), ("n", Simple("n")), ("stop", Simple("stop")),
    ("cd iris", TextCommand("cd", "iris")),
    ("claude fix tests", TextCommand("claude", "fix tests")),
    ("codex write docs", TextCommand("codex", "write docs")),
    ("forget abc", TextCommand("forget", "abc")),
    ("correct abc replacement", TextCommand("correct", "abc replacement")),
    ("@12 continue work", IndexedCommand("session_message", 12, "continue work")),
    ("kill 4", IndexedCommand("kill", 4)),
])
def test_grammar_recognizes_complete_command_set(text, expected):
    assert parse(text) == expected
