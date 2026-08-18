import threading
import time

from iris.approvals import ApprovalQueue


def test_yes_resolves_oldest_pending_request():
    notices = []
    queue = ApprovalQueue(notifier=notices.append)
    result = []
    thread = threading.Thread(target=lambda: result.append(queue.request("run git status", timeout=1)))
    thread.start()
    while not queue.pending():
        time.sleep(0.005)

    assert queue.resolve(True) is True
    thread.join(1)
    assert result == [True]
