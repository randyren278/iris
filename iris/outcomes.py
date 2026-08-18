import json, pathlib
class OutcomeLedger:
 def __init__(self,path): self.path=pathlib.Path(path)
 def append(self,capability,outcome):
  self.path.parent.mkdir(parents=True,exist_ok=True)
  with self.path.open("a") as f: f.write(json.dumps({"capability":capability,"outcome":outcome})+"\n")
 def entries(self): return tuple(json.loads(x) for x in self.path.read_text().splitlines()) if self.path.exists() else ()
