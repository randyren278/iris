import subprocess, sys
def test_master_conversation(): assert subprocess.call([sys.executable,"-m","pytest","tests/memory/test_conversation_turns.py","tests/sessions/test_session_streaming.py","tests/sessions/test_session_steering.py","-q"]) == 0
