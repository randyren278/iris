from iris.capabilities import CapabilityPolicy
def test_consequential_action_requires_explicit_approval():
 p=CapabilityPolicy(("send_message",)); assert not p.request("send_message",False) and p.request("send_message",True)
