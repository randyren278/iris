from iris.user_model import UserModel
def test_explanation_identifies_origin_and_confidence():
 m=UserModel(); m.add("a","short","stated",1); assert "stated" in m.explain("a")
