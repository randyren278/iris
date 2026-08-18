from iris.fallback import FallbackTranslator


def test_expired_proposal_cannot_be_confirmed():
    now = [0.0]
    fallback = FallbackTranslator(lambda _text: {"command": "stop"}, clock=lambda: now[0], ttl_seconds=10)
    fallback.propose("please stop")
    now[0] = 10.1

    assert fallback.confirm() is None
