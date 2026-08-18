from iris.output import split_for_slack


def test_output_burst_is_capped_with_a_readable_notice():
    messages = split_for_slack("one two four five", max_chars=4, max_messages=2)
    assert messages == ("one", "Output truncated; ask Iris to narrow the request.")
