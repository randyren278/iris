from iris.salience import SalienceEngine
def test_mute_takes_effect_immediately():
 sent=[]; e=SalienceEngine(shadow=False); e.mute(); assert not e.notify(e.score(deadline_hours=1),sent.append)
