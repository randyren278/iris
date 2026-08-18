from iris.salience import SalienceEngine
def test_shadow_mode_never_notifies():
 sent=[]; e=SalienceEngine(); assert not e.notify(e.score(deadline_hours=1),sent.append) and not sent
