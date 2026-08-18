import subprocess, sys
def test_master_senses(): assert subprocess.call([sys.executable,"-m","pytest","tests/test_calendar_sense.py","tests/test_sense_revoke.py","tests/test_sense_quarantine.py","-q"]) == 0
