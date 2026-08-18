import subprocess, sys
def test_master_trust(): assert subprocess.call([sys.executable,"-m","pytest","tests/memory/test_memory_trust_boundary.py","-q"]) == 0
