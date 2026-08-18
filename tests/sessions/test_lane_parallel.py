import threading

from iris.lanes import SessionLanes


def test_different_sessions_can_run_in_parallel():
    lanes = SessionLanes()
    both_started = threading.Barrier(3)
    release = threading.Event()

    first = lanes.submit(1, lambda: (both_started.wait(1), release.wait(1)))
    second = lanes.submit(2, lambda: (both_started.wait(1), release.wait(1)))
    both_started.wait(1)
    release.set()
    first.result(1)
    second.result(1)
    lanes.shutdown()
