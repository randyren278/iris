"""CP-3.3: an allowlisted handle is accepted."""
from iris.allowlist import Allowlist
from iris.config import Config

ALLOWED = "+15551234567"


def test_allowed_handle_passes():
    assert Allowlist([ALLOWED]).allows(ALLOWED)


def test_contains_operator_agrees_with_allows():
    a = Allowlist([ALLOWED])
    assert ALLOWED in a


def test_multiple_handles_all_allowed():
    handles = [ALLOWED, "friend@icloud.com", "+15559999999"]
    a = Allowlist(handles)
    assert all(a.allows(h) for h in handles)


def test_email_style_handle_allowed():
    assert Allowlist(["friend@icloud.com"]).allows("friend@icloud.com")


def test_built_from_config():
    cfg = Config(allowlist=(ALLOWED,))
    assert Allowlist.from_config(cfg).allows(ALLOWED)
