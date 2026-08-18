"""CP-3.5: the walking skeleton echoes an allowlisted fake arrival."""
from iris.config import Config
from iris.main import Gateway


def test_echo_roundtrip_fake(fakedb, sender, tmp_path):
    config = Config(chatdb=fakedb.path, state_path=tmp_path / "state.json",
                    sender=sender, allowlist=("+15551234567",))
    gateway = Gateway(config)
    gateway.run_once()  # establish the high-water mark before the arrival
    fakedb.inject("+15551234567", "hello iris")

    assert gateway.run_once() == [True]
    assert sender.last() == ("iMessage;-;+15551234567", "hello iris")
