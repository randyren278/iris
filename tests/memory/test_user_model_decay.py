from iris.user_model import UserModel
def test_stale_inferences_decay():
 m=UserModel(); m.add("a","short","inferred",.6); m.decay(99); assert m.inspect()[0].confidence==.3
