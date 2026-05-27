from __future__ import annotations

from pathlib import Path

import notes_recovery.services.fts as fts


def test_read_text_for_fts_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    text, truncated, label = fts.read_text_for_fts(missing, max_bytes=10, max_chars=50)
    assert text == ""
    assert truncated is False
    assert label == ""


def test_resolve_recovered_db_path_none(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    assert fts.resolve_recovered_db_path(root, None) is None


def test_ensure_fts5_available_short_circuit() -> None:
    class FakeCursor:
        def __init__(self, row):
            self._row = row

        def fetchone(self):
            return self._row

    class FakeConn:
        def execute(self, sql):
            if "sqlite_compileoption_used" in sql:
                return FakeCursor((1,))
            raise AssertionError("should not execute further")

    fts.ensure_fts5_available(FakeConn())
