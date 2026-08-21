import threading

from iris.approvals import ApprovalQueue
from tests.waiting import wait_until


def test_yes_resolves_oldest_pending_request():
    notices = []
    queue = ApprovalQueue(notifier=notices.append)
    result = []
    thread = threading.Thread(target=lambda: result.append(queue.request("run git status", timeout=1)))
    thread.start()
    wait_until(queue.pending, message="queue never received a pending approval")

    assert queue.resolve(True) is True
    thread.join(1)
    assert result == [True]
