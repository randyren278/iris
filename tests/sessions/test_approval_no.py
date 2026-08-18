import threading
import time

from iris.approvals import ApprovalQueue


def test_no_denies_pending_request():
    queue = ApprovalQueue(notifier=lambda _message: None)
    result = []
    thread = threading.Thread(target=lambda: result.append(queue.request("delete file", timeout=1)))
    thread.start()
    while not queue.pending():
        time.sleep(0.005)

    queue.resolve(False)
    thread.join(1)
    assert result == [False]
