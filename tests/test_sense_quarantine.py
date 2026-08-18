import pytest
from iris.senses import SenseStore, SourceItem
def test_source_cannot_claim_trusted_context(tmp_path):
 with pytest.raises(ValueError): SenseStore(tmp_path/"s.json").ingest_calendar((SourceItem("calendar","a","t","x","self"),))
