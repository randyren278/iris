from iris.outcomes import OutcomeLedger
def test_outcome_ledger_is_append_only(tmp_path):
 l=OutcomeLedger(tmp_path/"o"); l.append("x","one"); l.append("x","two"); assert len(l.entries())==2
