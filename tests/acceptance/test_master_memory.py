import subprocess, sys
def test_master_memory(): assert subprocess.call([sys.executable,"-m","pytest","tests/test_memory_records.py","tests/test_memory_corrections.py","tests/test_memory_forgetting.py","-q"]) == 0
