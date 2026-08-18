from iris.grammar import IndexedCommand, Simple, TextCommand, parse


def test_grammar_tolerates_case_and_extra_whitespace():
    assert parse("  PROJECTS  ") == Simple("projects")
    assert parse("  CoDeX   make   this  safe ") == TextCommand("codex", "make this safe")
    assert parse(" @7   status ") == IndexedCommand("session_message", 7, "status")
