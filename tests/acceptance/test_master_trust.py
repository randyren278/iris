import subprocess, sys
def test_master_trust(): assert subprocess.call([sys.executable,"-m","pytest","tests/test_memory_trust_boundary.py","-q"]) == 0
