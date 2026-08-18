import threading
import time
import uuid
from pathlib import Path

from iris.approvals import ApprovalQueue, ApprovalServer, request_approval


def test_hook_blocks_until_operator_decision(tmp_path):
    queue = ApprovalQueue(notifier=lambda _message: None)
    server = ApprovalServer(Path("/tmp") / f"iris-{uuid.uuid4().hex}.sock", queue, timeout=1)
    server.start()
    result = []
    thread = threading.Thread(target=lambda: result.append(request_approval(server.path, "run tool")))
    thread.start()
    while not queue.pending():
        time.sleep(0.005)
    assert thread.is_alive()
    queue.resolve(True)
    thread.join(1)
    server.close()
    assert result == [True]
