from iris.fallback import FallbackTranslator


def test_proposal_never_executes_during_translation():
    executed = []
    fallback = FallbackTranslator(lambda _text: {"command": "stop"})

    fallback.propose("stop it")

    assert executed == []
