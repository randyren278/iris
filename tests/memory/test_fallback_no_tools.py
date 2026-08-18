from iris.fallback import FallbackTranslator


def test_fallback_does_not_receive_or_invoke_tools():
    calls = []
    fallback = FallbackTranslator(lambda text: calls.append(text) or {"command": "projects"})

    fallback.propose("show projects")

    assert calls == ["show projects"]
