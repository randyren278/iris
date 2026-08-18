from types import SimpleNamespace

from iris.notifications import OriginThreadNotifier
from tests.slack_fakes import RecordingSlackClient


def test_approval_notice_is_delivered_to_the_originating_dm_thread():
    client = RecordingSlackClient()
    notifier = OriginThreadNotifier(client)
    assert not notifier.notify("Approval 1")
    notifier.observe(SimpleNamespace(channel_id="D-1", reply_thread_ts="1.1"))

    assert notifier.notify("Approval 1: write file")
    assert client.messages == [{"channel_id": "D-1", "thread_ts": "1.1", "text": "Approval 1: write file"}]
