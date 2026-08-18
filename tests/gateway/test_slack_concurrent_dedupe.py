"""Socket Mode dispatches socket_mode_request_listeners from a thread pool
(slack_sdk.socket_mode.client.enqueue_message -> message_workers.submit), so
SlackGateway.handle_envelope can run concurrently on multiple threads for the
same event_id during a Slack retry/reconnect. The event-id dedupe set must
not let two threads both pass the "not seen yet" check before either records
the id, or the same inbound command gets processed and posted twice.

A pure thread-scheduling race on a two-statement window ("x in set" then
"set.add(x)") is too small to hit reliably by luck under the GIL, so this
test forces the interleaving deterministically: it wraps the dedupe set's
membership check with a two-party rendezvous. If two threads reach the check
concurrently (no lock serializes them), they rendezvous and both observe
"not seen" -- reproducing the real race. If a lock serializes access, only
one thread can ever reach the check at a time, so the rendezvous times out
and each thread falls through to the real (correct) answer.
"""
import threading

from iris.slack import SlackGateway
from tests.gateway.test_slack_echo_e2e import dm_envelope
from tests.slack_fakes import RecordingSlackClient


class _RendezvousSet(set):
    """A set whose membership check offers a brief rendezvous window on
    both sides of the read, so two concurrent callers both read the set
    state before either caller's subsequent `add()` can be observed --
    reproducing an unsynchronized check-then-act race. A caller that
    arrives alone (because something else serializes access) simply times
    out on each barrier and gets the real, current answer.
    """

    def __init__(self):
        super().__init__()
        self._enter = threading.Barrier(2, timeout=0.2)
        self._leave = threading.Barrier(2, timeout=0.2)

    def __contains__(self, item):
        try:
            self._enter.wait()
        except threading.BrokenBarrierError:
            pass
        result = super().__contains__(item)
        try:
            self._leave.wait()
        except threading.BrokenBarrierError:
            pass
        return result


def test_concurrent_delivery_of_the_same_event_is_processed_once():
    client = RecordingSlackClient()
    gateway = SlackGateway(["U-allowed"], client)
    gateway._seen_event_ids = _RendezvousSet()
    envelope = dm_envelope(event_id="Ev-race")

    start = threading.Barrier(2)
    results = [None, None]

    def worker(index):
        start.wait()
        results[index] = gateway.handle_envelope(envelope)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(True) == 1
    assert len(client.messages) == 1
