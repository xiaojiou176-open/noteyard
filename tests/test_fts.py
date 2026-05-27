import sqlite3
from pathlib import Path

import pytest

from notes_recovery.services.fts import ensure_fts5_available, iter_fts_text_files, read_text_for_fts


def test_read_text_for_fts(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("hello world", encoding="utf-8")
    text, truncated, label = read_text_for_fts(path, 1024, 200)
    assert "hello" in text
    assert truncated is False
    assert label


def test_iter_fts_text_files(tmp_path: Path) -> None:
    root = tmp_path / "Notes_Forensics"
    blob_dir = root / "Recovered_Blobs"
    blob_dir.mkdir(parents=True)
    (blob_dir / "blob_0001.txt").write_text("hello", encoding="utf-8")
    files = list(iter_fts_text_files(root, max_file_mb=1))
    assert files


def test_ensure_fts5_available() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        try:
            ensure_fts5_available(conn)
        except RuntimeError:
            pytest.skip("FTS5 not available in current sqlite3")
    finally:
        conn.close()
