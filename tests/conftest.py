"""Configure un SQLite isolé avant l’import de l’app."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_db = Path(tempfile.gettempdir()) / f"openyard-pytest-{os.getpid()}.db"
if _db.exists():
    _db.unlink()
os.environ["OPENYARD_DB"] = str(_db)
os.environ.setdefault("OPENYARD_CLUSTER", "false")
os.environ.setdefault("OPENYARD_COMPUTE", "sim")
