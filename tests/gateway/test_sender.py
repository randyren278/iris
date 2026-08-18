"""CP-3.4: sender reports successful and exhausted delivery attempts."""
from types import SimpleNamespace

import pytest

from iris.sender import send


def test_sender_returns_true_when_osascript_succeeds():
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    assert send("friend@icloud.com", "hello", runner=runner) is True
    assert len(calls) == 1


def test_sender_returns_false_after_exhausting_attempts():
    calls, sleeps = [], []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1)

    assert send("friend@icloud.com", "hello", attempts=3, retry_delay=.25,
                runner=runner, sleeper=sleeps.append) is False
    assert len(calls) == 3
    assert sleeps == [.25, .5]


@pytest.mark.parametrize("handle,text", [("", "x"), (None, "x"), ("h", None)])
def test_sender_rejects_invalid_arguments(handle, text):
    with pytest.raises(ValueError):
        send(handle, text)
