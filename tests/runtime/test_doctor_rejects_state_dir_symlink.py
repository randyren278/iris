import pytest

from iris.doctor import ensure_private_state_dir


def test_ensure_private_state_dir_refuses_to_follow_a_symlink(tmp_path):
    real_target = tmp_path / "elsewhere"
    real_target.mkdir()
    real_target.chmod(0o777)
    link = tmp_path / "state"
    link.symlink_to(real_target)

    with pytest.raises(OSError):
        ensure_private_state_dir(link)

    # The attacker-controlled directory must be left alone, not "fixed" in place.
    assert real_target.stat().st_mode & 0o777 == 0o777
