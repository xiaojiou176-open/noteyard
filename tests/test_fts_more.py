from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from notes_recovery.services import fts


def _create_recovered_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE ZICCLOUDSYNCINGOBJECT (ZTITLE1 TEXT, ZSNIPPET TEXT)")
    conn.execute("INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES (?, ?)", ("Title", "secret snippet"))
    conn.commit()
    conn.close()


def test_build_fts_index_all_sources(tmp_path: Path, monkeypatch) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    (root_dir / "Recovered_Notes").mkdir(parents=True)
    (root_dir / "Recovered_DB").mkdir(parents=True)

    text_file = root_dir / "Recovered_Notes" / "note.txt"
    text_file.write_text("secret in notes", encoding="utf-8")

    db_path = root_dir / "Recovered_DB" / "notes.sqlite"
    _create_recovered_db(db_path)

    out_dir = tmp_path / "out"

    # Guard if FTS5 is not available in this environment.
    conn = sqlite3.connect(":memory:")
    try:
        fts.ensure_fts5_available(conn)
    except RuntimeError:
        pytest.skip("SQLite FTS5 is unavailable in this environment.")
    finally:
        conn.close()

    fts_db = fts.build_fts_index(
        root_dir=root_dir,
        out_dir=out_dir,
        keyword="secret",
        source_mode="all",
        db_path=None,
        db_table=None,
        db_columns=[],
        db_title_column=None,
        max_docs=10,
        max_file_mb=1,
        max_text_chars=200,
    )
    assert fts_db.exists()
    assert (out_dir / "fts_summary.md").exists()


def test_read_text_for_fts_html(tmp_path: Path) -> None:
    html_path = tmp_path / "sample.html"
    html_path.write_text("<p>hello</p>", encoding="utf-8")
    text, truncated, label = fts.read_text_for_fts(html_path, max_bytes=100, max_chars=200)
    assert "hello" in text
    assert truncated is False
    assert label


def test_ensure_fts5_unavailable(monkeypatch) -> None:
    class _FakeConn:
        def execute(self, _sql):
            raise sqlite3.OperationalError("no fts5")

    with pytest.raises(RuntimeError):
        fts.ensure_fts5_available(_FakeConn())


def test_read_text_for_fts_empty_and_missing(tmp_path: Path) -> None:
    empty_path = tmp_path / "empty.txt"
    empty_path.write_text("", encoding="utf-8")
    text, truncated, label = fts.read_text_for_fts(empty_path, max_bytes=10, max_chars=50)
    assert text == ""
    assert truncated is False
    assert label == ""
    text, truncated, label = fts.read_text_for_fts(tmp_path / "missing.txt", max_bytes=10, max_chars=50)
    assert text == ""


def test_iter_fts_text_files_and_resolve_db(tmp_path: Path) -> None:
    root = tmp_path / "Notes_Forensics"
    (root / "Recovered_Notes").mkdir(parents=True)
    small = root / "Recovered_Notes" / "note.txt"
    small.write_text("hello", encoding="utf-8")
    big = root / "Recovered_Notes" / "big.txt"
    big.write_bytes(b"x" * (2 * 1024 * 1024))
    files = list(fts.iter_fts_text_files(root, max_file_mb=1))
    assert small in files
    assert big not in files

    assert fts.resolve_recovered_db_path(root, None) is None
    assert fts.resolve_recovered_db_path(root, small) == small


def test_safe_path_mtime_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    assert fts.safe_path_mtime(missing) == 0.0
