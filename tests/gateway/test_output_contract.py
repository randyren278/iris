import pytest

from iris.output import split_for_slack


def test_splitter_rejects_nontext_and_nonpositive_limits():
    with pytest.raises(TypeError, match="text must be a string"):
        split_for_slack(None)
    for kwargs in ({"max_chars": 0}, {"max_chars": -1}, {"max_messages": 0}):
        with pytest.raises(ValueError, match="message limits must be positive"):
            split_for_slack("hello", **kwargs)


def test_splitter_returns_no_messages_for_whitespace_only_text():
    assert split_for_slack("") == ()
    assert split_for_slack(" \n \t ") == ()


def test_splitter_preserves_words_and_breaks_at_whitespace():
    assert split_for_slack("one two three four", max_chars=7, max_messages=10) == (
        "one two", "three", "four"
    )


def test_splitter_accepts_exact_limit_and_rejects_oversized_single_word():
    assert split_for_slack("abcd", max_chars=4) == ("abcd",)
    with pytest.raises(ValueError, match="one word exceeds"):
        split_for_slack("abcde", max_chars=4)


def test_splitter_truncates_burst_with_explicit_notice():
    result = split_for_slack("aa bb cc dd ee", max_chars=2, max_messages=3)
    assert result == ("aa", "bb", "Output truncated; ask Iris to narrow the request.")


def test_one_message_limit_returns_only_truncation_notice_when_multiple_chunks_needed():
    assert split_for_slack("aa bb", max_chars=2, max_messages=1) == (
        "Output truncated; ask Iris to narrow the request.",
    )
