from iris.output import split_for_slack


def test_streamed_agent_output_uses_the_same_bounded_slack_renderer():
    chunks = split_for_slack("one two three four", max_chars=7, max_messages=2)
    assert chunks == ("one two", "Output truncated; ask Iris to narrow the request.")
