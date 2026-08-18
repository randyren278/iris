"""CP-3.4: retry behavior is bounded and stops immediately on success."""
from types import SimpleNamespace

from iris.sender import send


def test_sender_stops_retrying_after_a_later_success():
    results = iter([1, 0])
    calls, sleeps = [], []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=next(results))

    assert send("friend@icloud.com", "hello", attempts=3, runner=runner,
                sleeper=sleeps.append)
    assert len(calls) == 2
    assert sleeps == [.5]


def test_sender_never_retries_more_than_requested():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1)

    assert not send("friend@icloud.com", "hello", attempts=1, runner=runner)
    assert len(calls) == 1
