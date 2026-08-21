"""Bounded waits for tests that hand work to a background thread.

An unbounded `while not queue.pending(): time.sleep(...)` busy-wait turns any
regression that stops the approval from ever being queued into a hung suite
rather than a failing test. That is what the safety mutation guard trips over:
it runs the suite once per mutation, so a single hang stalls the whole job
until CI kills it, with no indication of which invariant was involved.
"""
from __future__ import annotations

import time

DEFAULT_TIMEOUT = 5.0


def wait_until(predicate, *, timeout: float = DEFAULT_TIMEOUT, message: str = "") -> None:
    """Block until `predicate()` is truthy, or fail the test after `timeout`."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError(
                f"condition not met within {timeout}s: {message or predicate!r}")
        time.sleep(0.005)
