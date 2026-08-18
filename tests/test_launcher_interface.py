from iris.launcher import Launcher


def test_launcher_rejects_unknown_tool_and_invalid_launches(tmp_path):
    launcher = Launcher(popen=lambda *_args, **_kwargs: None)

    for tool, cwd, prompt in [("other", tmp_path, "go"), ("claude", tmp_path / "missing", "go"),
                              ("codex", tmp_path, "")]:
        try:
            launcher.launch(tool, cwd=cwd, prompt=prompt)
        except ValueError:
            pass
        else:  # pragma: no cover - failure branch
            raise AssertionError("invalid launch was accepted")
