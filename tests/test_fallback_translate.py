from iris.fallback import FallbackTranslator
from iris.grammar import TextCommand


def test_fallback_returns_a_valid_proposal_only():
    fallback = FallbackTranslator(lambda _text: {"command": "cd iris"})

    proposal = fallback.propose("open iris")

    assert proposal is not None
    assert proposal.command == TextCommand("cd", "iris")
