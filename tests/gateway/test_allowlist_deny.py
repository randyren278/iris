"""CP-3.3: everything not on the list is dropped."""
from iris.allowlist import Allowlist

ALLOWED = "+15551234567"


def test_unknown_handle_dropped():
    assert not Allowlist([ALLOWED]).allows("+15550000000")


def test_empty_allowlist_denies_everyone():
    a = Allowlist()
    assert not a.allows(ALLOWED)
    assert len(a) == 0


def test_none_handle_denied():
    """An unmatched handle join yields NULL; it must not crash or pass."""
    assert not Allowlist([ALLOWED]).allows(None)


def test_empty_string_denied():
    assert not Allowlist([ALLOWED]).allows("")


def test_non_string_handle_denied():
    assert not Allowlist([ALLOWED]).allows(15551234567)
