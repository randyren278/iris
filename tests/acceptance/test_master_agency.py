import subprocess
import sys


AGENCY_CONTRACT = [
    "tests/agent/test_agent_actions.py",
    "tests/agent/test_claude_mcp_adapter.py",
    "tests/agent/test_mcp_server.py",
    "tests/acceptance/test_agentic_hardening.py",
    "tests/sessions/test_capability_approvals.py",
    "tests/memory/test_no_self_escalation.py",
]


def test_master_agency():
    assert subprocess.call([sys.executable, "-m", "pytest", *AGENCY_CONTRACT, "-q"]) == 0
