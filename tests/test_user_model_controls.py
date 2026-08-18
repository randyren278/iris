from iris.user_model import UserModel
def test_operator_can_inspect_and_delete_entry():
 m=UserModel(); m.add("a","short","stated",1); m.delete("a"); assert m.inspect()==()
