"""Narrow adapter for exporting approved Iris claims to Hera sources."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile

from iris.memory import MemoryRecord


class HeraMemoryAdapter:
    def __init__(self, hera_root: pathlib.Path | str, *, run=subprocess.run):
        self.root, self._run = pathlib.Path(hera_root), run

    def ingest(self, record: MemoryRecord) -> None:
        if record.trust not in {"self", "team"} or record.authoring_mode != "operator_confirmed":
            raise ValueError("only approved trusted claims may reach Hera")
        payload = json.dumps({"claim": record.claim, "source_ref": record.source_ref,
                              "trust": record.trust, "memory_id": record.id})
        handle, source = tempfile.mkstemp(prefix="iris-memory-", suffix=".json")
        try:
            with os.fdopen(handle, "w") as stream:
                stream.write(payload)
            self._run([str(self.root / ".venv/bin/python"), "scripts/ingest.py", source,
                       "--kind", "iris-memory", "--trust", record.trust],
                      cwd=self.root, check=True, capture_output=True, text=True)
        finally:
            if os.path.exists(source):
                os.unlink(source)
