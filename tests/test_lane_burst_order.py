from iris.lanes import SessionLanes


def test_burst_for_one_session_preserves_submission_order():
    lanes = SessionLanes()
    seen = []
    futures = [lanes.submit(9, seen.append, number) for number in range(20)]
    for future in futures:
        future.result(1)
    lanes.shutdown()
    assert seen == list(range(20))
