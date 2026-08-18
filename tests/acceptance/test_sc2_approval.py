import threading
import time

from iris.approvals import ApprovalQueue


def test_pending_tool_call_can_be_approved_by_operator_response():
    queue = ApprovalQueue(notifier=lambda _message: None)
    result = []
    waiting = threading.Thread(target=lambda: result.append(queue.request("write file", timeout=1)))
    waiting.start()
    while not queue.pending():
        time.sleep(0.005)

    queue.resolve(True)
    waiting.join(1)

    assert result == [True]
