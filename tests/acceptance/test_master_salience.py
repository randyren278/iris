import subprocess, sys
def test_master_salience(): assert subprocess.call([sys.executable,"-m","pytest","tests/test_salience_explanations.py","tests/test_salience_shadow_mode.py","tests/test_salience_controls.py","-q"]) == 0
