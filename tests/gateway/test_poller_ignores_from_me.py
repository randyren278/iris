"""CP-3.2: Iris must not read its own replies back as commands.

Outbound rows land in the same table. Without this filter the gateway would
answer itself -- an echo loop in the literal sense.
"""
import pytest

from iris.poller import Poller


@pytest.fixture
def poller(fakedb, tmp_path):
    p = Poller(fakedb.path, tmp_path / "state.json")
    p.poll_once()
    return p


def test_ignores_outbound(fakedb, poller):
    fakedb.inject("+15551234567", "iris said this", is_from_me=1)
    assert poller.poll_once() == []


def test_yields_inbound_but_not_the_reply(fakedb, poller):
    fakedb.inject("+15551234567", "operator asks", is_from_me=0)
    fakedb.inject("+15551234567", "iris answers", is_from_me=1)
    assert [m.body for m in poller.poll_once()] == ["operator asks"]


def test_outbound_still_advances_the_high_water(fakedb, poller):
    """An ignored row must not be re-examined forever."""
    fakedb.inject("+15551234567", "iris answers", is_from_me=1)
    assert poller.poll_once() == []
    assert poller.poll_once() == []
    fakedb.inject("+15551234567", "operator asks")
    assert [m.body for m in poller.poll_once()] == ["operator asks"]
