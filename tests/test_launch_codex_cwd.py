from iris.launcher import Launcher


class Process:
    pid = 43


def test_codex_launch_uses_selected_project_as_cwd(tmp_path):
    calls = []
    launcher = Launcher(popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process())

    launcher.launch("codex", cwd=tmp_path, prompt="write docs")

    assert calls[0][0][0] == ["codex", "write docs"]
    assert calls[0][1]["cwd"] == str(tmp_path.resolve())
