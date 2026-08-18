from iris.output import split_for_slack


def test_short_output_stays_a_single_message():
    assert split_for_slack("short status") == ("short status",)
