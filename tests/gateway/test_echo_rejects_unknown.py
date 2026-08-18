"""CP-3.5: a non-allowlisted sender receives no reply."""
from iris.config import Config
from iris.main import Gateway


def test_unknown_sender_no_echo(fakedb, sender, tmp_path):
    config = Config(chatdb=fakedb.path, state_path=tmp_path / "state.json",
                    sender=sender, allowlist=("+15551234567",))
    gateway = Gateway(config)
    gateway.run_once()
    fakedb.inject("+15550000000", "start a shell")

    assert gateway.run_once() == [False]
    assert sender.sent == []
