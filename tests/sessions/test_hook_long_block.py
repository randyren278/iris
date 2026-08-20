import threading
import time
import uuid
from pathlib import Path

from iris.approvals import ApprovalQueue, ApprovalServer, request_approval
from tests.waiting import wait_until


def test_hook_supports_a_longer_wait_than_connect_timeout(tmp_path):
    queue = ApprovalQueue(notifier=lambda _message: None)
    server = ApprovalServer(Path("/tmp") / f"iris-{uuid.uuid4().hex}.sock", queue, timeout=1)
    server.start()
    result = []
    thread = threading.Thread(target=lambda: result.append(request_approval(server.path, "run tool", connect_timeout=0.05)))
    thread.start()
    wait_until(queue.pending, message="queue never received a pending approval")
    time.sleep(0.08)
    queue.resolve(True)
    thread.join(1)
    server.close()
    assert result == [True]
