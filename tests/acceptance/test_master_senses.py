import subprocess, sys
def test_master_senses(): assert subprocess.call([sys.executable,"-m","pytest","tests/senses/test_calendar_sense.py","tests/senses/test_sense_revoke.py","tests/senses/test_sense_quarantine.py","-q"]) == 0
