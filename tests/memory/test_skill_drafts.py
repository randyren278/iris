import pathlib
def test_drafted_skills_cannot_autoload(tmp_path):
 draft=tmp_path/"skill-drafts"/"x"; draft.mkdir(parents=True); (draft/"SKILL.md").write_text("draft")
 assert not (tmp_path/"skills"/"x"/"SKILL.md").exists()
