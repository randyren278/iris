import pathlib
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


@pytest.fixture
def socket_dir():
    """A short-path directory for tests that actually bind an AF_UNIX socket.

    macOS caps AF_UNIX paths at 104 bytes, and pytest's `tmp_path` alone is
    already longer than that, so binding under `tmp_path` fails with
    `OSError: AF_UNIX path too long`. Tests that only need a socket *path*
    (never bound) can keep using `tmp_path`.
    """
    path = pathlib.Path(tempfile.mkdtemp(prefix="iris-", dir="/tmp"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
