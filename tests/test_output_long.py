from iris.output import split_for_slack


def test_long_output_splits_at_words_not_mid_word():
    messages = split_for_slack("alpha bravo charlie delta", max_chars=12)
    assert messages == ("alpha bravo", "charlie", "delta")
