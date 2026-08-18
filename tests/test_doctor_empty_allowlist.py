from iris.config import Config
from iris.doctor import diagnose, ensure_private_state_dir


def test_doctor_reports_empty_slack_allowlist(tmp_path):
    state = ensure_private_state_dir(tmp_path / "state")

    assert diagnose(Config(), state) == ("Slack allowlist is empty",)
