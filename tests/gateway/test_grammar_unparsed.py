import pytest

from iris.grammar import parse


@pytest.mark.parametrize("text", ["", "hello iris", "claude", "kill nope", "@0", "rm -rf /"])
def test_unknown_input_is_unparsed(text):
    assert parse(text) is None
