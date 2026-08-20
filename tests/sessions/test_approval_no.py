import threading

from iris.approvals import ApprovalQueue
from tests.waiting import wait_until


def test_no_denies_pending_request():
    queue = ApprovalQueue(notifier=lambda _message: None)
    result = []
    thread = threading.Thread(target=lambda: result.append(queue.request("delete file", timeout=1)))
    thread.start()
    wait_until(queue.pending, message="queue never received a pending approval")

    queue.resolve(False)
    thread.join(1)
    assert result == [False]
