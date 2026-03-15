"""Append-only ledger for decision records."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .schemas import LedgerEntry


class Ledger:
    """Append-only JSON ledger backed by a local file.

    Writes use atomic rename (write to temp, then rename) to prevent corruption.
    """

    def __init__(self, path: str = "ledger.json"):
        self.path = Path(path)
        if not self.path.exists():
            self._write_entries([])

    def append(self, entry: LedgerEntry) -> None:
        """Append a single entry to the ledger. Never modifies existing entries."""
        entries = self._read_entries()
        entries.append(json.loads(entry.model_dump_json()))
        self._write_entries(entries)

    def read_all(self) -> list[dict]:
        """Read all ledger entries."""
        return self._read_entries()

    def _read_entries(self) -> list[dict]:
        with open(self.path, "r") as f:
            return json.load(f)

    def _write_entries(self, entries: list[dict]) -> None:
        """Atomic write: write to temp file, then rename."""
        dir_path = self.path.parent
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(entries, f, indent=2, default=str)
            os.replace(tmp_path, self.path)
        except Exception:
            os.unlink(tmp_path)
            raise
