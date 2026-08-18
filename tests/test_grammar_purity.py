from iris.grammar import parse


def test_parse_has_no_input_mutation_or_state():
    text = "  claude   inspect  "

    first = parse(text)
    second = parse(text)

    assert text == "  claude   inspect  "
    assert first == second
