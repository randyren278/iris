from iris.salience import SalienceEngine
def test_score_has_explanation_and_provenance():
 c=SalienceEngine().score(deadline_hours=3,conflict=True); assert c.explanation and c.source=="calendar"
