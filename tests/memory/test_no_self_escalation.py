from iris.capabilities import CapabilityPolicy
def test_policy_cannot_self_expand():
 assert not CapabilityPolicy().request("send_message",True)
