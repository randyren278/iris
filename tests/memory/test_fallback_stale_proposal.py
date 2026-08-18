from iris.fallback import FallbackTranslator


def test_failed_reproposal_clears_a_previously_pending_proposal():
    responses = iter([{"command": "stop"}, {"command": "not a real command"}])
    fallback = FallbackTranslator(lambda _text: next(responses))

    first = fallback.propose("stop it")
    assert first is not None

    second = fallback.propose("something unrelated")
    assert second is None

    assert fallback.confirm() is None
