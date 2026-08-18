import threading
import time

from iris.lanes import SessionLanes


def test_same_session_work_is_serialized():
    lanes = SessionLanes()
    entered = threading.Event()
    release = threading.Event()
    order = []

    first = lanes.submit(1, lambda: (order.append("first"), entered.set(), release.wait(), order.append("done")))
    entered.wait(1)
    second = lanes.submit(1, lambda: order.append("second"))
    time.sleep(0.02)
    assert order == ["first"]
    release.set()
    first.result(1)
    second.result(1)
    lanes.shutdown()
    assert order == ["first", "done", "second"]
