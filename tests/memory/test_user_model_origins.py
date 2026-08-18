import pytest
from iris.user_model import UserModel
def test_origins_are_separate_and_inferences_bounded():
 m=UserModel(); assert m.add("a","short","stated",1).origin=="stated"
 with pytest.raises(ValueError): m.add("b","x","inferred",.9)
