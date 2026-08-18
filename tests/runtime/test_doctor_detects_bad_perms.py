from iris.config import Config
from iris.doctor import diagnose


def test_doctor_detects_insecure_state_directory_permissions(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    state.chmod(0o755)

    assert "state directory permissions must be 700" in diagnose(Config(slack_allowlist=("U-1",)), state)
