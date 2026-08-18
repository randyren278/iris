from iris.fallback import FallbackTranslator
from iris.grammar import Simple


def test_confirm_returns_pending_command_once():
    fallback = FallbackTranslator(lambda _text: {"command": "projects"})
    fallback.propose("show my projects")

    assert fallback.confirm() == Simple("projects")
    assert fallback.confirm() is None
