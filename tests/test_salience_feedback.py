from iris.salience import SalienceEngine
def test_feedback_improves_ranked_fixture():
 e=SalienceEngine(); c=e.score(deadline_hours=1); assert e.feedback(c,True).score>c.score
