import threading
import time

from iris.approvals import ApprovalQueue


def test_indexed_decision_targets_selected_pending_request():
    queue = ApprovalQueue(notifier=lambda _message: None)
    first, second = [], []
    first_thread = threading.Thread(target=lambda: first.append(queue.request("one", timeout=1)))
    second_thread = threading.Thread(target=lambda: second.append(queue.request("two", timeout=1)))
    first_thread.start()
    while len(queue.pending()) != 1:
        time.sleep(0.005)
    second_thread.start()
    while len(queue.pending()) != 2:
        time.sleep(0.005)

    assert queue.resolve(True, index=2) is True
    assert queue.resolve(False, index=1) is True
    first_thread.join(1)
    second_thread.join(1)
    assert first == [False]
    assert second == [True]
