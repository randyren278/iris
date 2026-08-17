import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tests.fakedb import FakeChatDB  # noqa: E402
from tests.fakesend import FakeSender  # noqa: E402


@pytest.fixture
def fakedb(tmp_path):
    return FakeChatDB(tmp_path / "chat.db")


@pytest.fixture
def sender():
    return FakeSender()
