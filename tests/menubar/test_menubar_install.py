"""Installing the menu bar indicator is a reversible, repeatable copy.

SWIFTBAR_PLUGIN_DIR redirects the destination, so these tests never touch the
real SwiftBar plugin directory or the running menu bar.
"""
import os
import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]
INSTALLER = REPO / "scripts" / "menubar" / "install-plugin.sh"
PLUGIN = "iris.30s.sh"


def run(action, plugin_dir):
    return subprocess.run([str(INSTALLER), action], capture_output=True, text=True,
                          env=dict(os.environ, SWIFTBAR_PLUGIN_DIR=str(plugin_dir)))


def test_install_places_an_executable_copy(tmp_path):
    result = run("install", tmp_path)
    assert result.returncode == 0, result.stderr
    installed = tmp_path / PLUGIN
    assert installed.is_file()
    assert os.access(installed, os.X_OK)
    assert installed.read_text() == (REPO / "scripts" / "menubar" / PLUGIN).read_text()


def test_install_creates_a_missing_plugin_directory(tmp_path):
    plugin_dir = tmp_path / "not-yet-there"
    assert run("install", plugin_dir).returncode == 0
    assert (plugin_dir / PLUGIN).is_file()


def test_install_is_idempotent(tmp_path):
    assert run("install", tmp_path).returncode == 0
    assert run("install", tmp_path).returncode == 0
    assert (tmp_path / PLUGIN).is_file()


def test_remove_takes_the_plugin_back_out(tmp_path):
    run("install", tmp_path)
    assert run("remove", tmp_path).returncode == 0
    assert not (tmp_path / PLUGIN).exists()


def test_remove_is_safe_when_nothing_is_installed(tmp_path):
    assert run("remove", tmp_path).returncode == 0


def test_remove_leaves_other_plugins_alone(tmp_path):
    neighbour = tmp_path / "straits.10m.sh"
    neighbour.write_text("#!/bin/bash\necho other\n")
    run("install", tmp_path)
    run("remove", tmp_path)
    assert neighbour.is_file()


def test_unknown_action_is_rejected(tmp_path):
    result = run("publish", tmp_path)
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_installers_wire_the_menu_bar_in_and_out():
    assert "menubar/install-plugin.sh" in (REPO / "scripts" / "install.sh").read_text()
    assert "install-plugin.sh" in (REPO / "scripts" / "uninstall.sh").read_text()
