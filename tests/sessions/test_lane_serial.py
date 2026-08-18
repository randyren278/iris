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


def test_lane_recovers_after_a_failed_job():
    """A failed job must not permanently poison the lane for later submissions."""
    lanes = SessionLanes()

    def boom():
        raise ValueError("boom")

    first = lanes.submit(1, boom)
    try:
        first.result(1)
        assert False, "expected ValueError"
    except ValueError:
        pass

    second = lanes.submit(1, lambda: "ok")
    assert second.result(1) == "ok"
    lanes.shutdown()
