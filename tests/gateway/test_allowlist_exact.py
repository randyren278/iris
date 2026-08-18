"""CP-3.3: matching is exact -- no prefix, substring, or normalisation.

Each case here is a handle an attacker could plausibly present. A loose
comparison would let any of them through to a shell on the operator's machine.
"""
import pytest

from iris.allowlist import Allowlist

ALLOWED = "+15551234567"


@pytest.mark.parametrize("impostor", [
    "+155512345678",              # allowed value is a prefix of this
    "+1555123456",                # this is a prefix of the allowed value
    "1555123467",                 # missing +1
    " +15551234567",              # leading space
    "+15551234567 ",              # trailing space
    "+15551234567@evil.com",      # allowed value as a substring
    "evil+15551234567",           # allowed value embedded
    "+1 555 123 4567",            # spaced formatting
    "+1-555-123-4567",            # dashed formatting
    "(555) 123-4567",             # local formatting
    "+15551234567\n",             # trailing newline
    "+1555123456X",               # single-char substitution
])
def test_no_substring_or_prefix_match(impostor):
    assert not Allowlist([ALLOWED]).allows(impostor)


def test_case_sensitive_for_email_handles():
    assert not Allowlist(["friend@icloud.com"]).allows("FRIEND@ICLOUD.COM")


def test_the_exact_value_still_passes():
    """Guard against a check so strict it rejects the real handle too."""
    assert Allowlist([ALLOWED]).allows(ALLOWED)
