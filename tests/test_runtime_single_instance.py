import os

from iris.runtime import RuntimeSupervisor


def test_second_runtime_cannot_claim_the_same_socket_mode_owner(tmp_path):
    first = RuntimeSupervisor(tmp_path, pid=os.getpid)
    second = RuntimeSupervisor(tmp_path, pid=os.getpid)
    assert first.start()
    assert not second.start()
    first.close()
    assert second.start()
