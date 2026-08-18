from iris.launcher import Launcher


class Process:
    pid = 42


def test_claude_launch_uses_selected_project_as_cwd(tmp_path):
    calls = []
    launcher = Launcher(popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process())

    launcher.launch("claude", cwd=tmp_path, prompt="fix tests")

    assert calls[0][1]["cwd"] == str(tmp_path.resolve())
