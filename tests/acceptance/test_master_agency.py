import subprocess, sys
def test_master_agency(): assert subprocess.call([sys.executable,"-m","pytest","tests/sessions/test_capability_approvals.py","tests/memory/test_no_self_escalation.py","-q"]) == 0
