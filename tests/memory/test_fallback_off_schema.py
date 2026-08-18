from iris.fallback import FallbackTranslator


def test_off_schema_or_unparsed_fallback_is_rejected():
    assert FallbackTranslator(lambda _text: {"command": "stop", "extra": True}).propose("halt") is None
    assert FallbackTranslator(lambda _text: {"command": "delete everything"}).propose("halt") is None
