import threading

from iris.approvals import ApprovalQueue
from tests.waiting import wait_until


def test_pending_tool_call_can_be_approved_by_operator_response():
    queue = ApprovalQueue(notifier=lambda _message: None)
    result = []
    waiting = threading.Thread(target=lambda: result.append(queue.request("write file", timeout=1)))
    waiting.start()
    wait_until(queue.pending, message="queue never received a pending approval")

    queue.resolve(True)
    waiting.join(1)

    assert result == [True]
