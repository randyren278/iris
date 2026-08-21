import threading

from iris.approvals import ApprovalQueue
from tests.waiting import wait_until


def test_indexed_decision_targets_selected_pending_request():
    queue = ApprovalQueue(notifier=lambda _message: None)
    first, second = [], []
    first_thread = threading.Thread(target=lambda: first.append(queue.request("one", timeout=1)))
    second_thread = threading.Thread(target=lambda: second.append(queue.request("two", timeout=1)))
    first_thread.start()
    wait_until(lambda: len(queue.pending()) == 1, message="queue never reached 1 pending approval(s)")
    second_thread.start()
    wait_until(lambda: len(queue.pending()) == 2, message="queue never reached 2 pending approval(s)")

    assert queue.resolve(True, index=2) is True
    assert queue.resolve(False, index=1) is True
    first_thread.join(1)
    second_thread.join(1)
    assert first == [False]
    assert second == [True]
