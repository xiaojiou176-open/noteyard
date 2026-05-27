import sqlite3
from pathlib import Path

from notes_recovery.services.query import query_notes


def test_query_legacy_schema(tmp_path: Path) -> None:
    legacy_db = Path(__file__).parent / "data" / "legacy_min.sqlite"
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    query_notes(legacy_db, keyword=None, out_dir=out_dir, run_ts="20260101_000000")
    outputs = list(out_dir.glob("legacy_recent_notes_*.csv"))
    assert outputs


def test_query_unknown_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE foo (id INTEGER)")
    conn.commit()
    conn.close()

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    query_notes(db_path, keyword=None, out_dir=out_dir, run_ts="20260101_000000")
    diagnostics = list(out_dir.glob("schema_diagnostics_*.csv"))
    assert diagnostics


def test_query_icloud_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "icloud.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE ZICCLOUDSYNCINGOBJECT ("
        "Z_PK INTEGER, ZIDENTIFIER TEXT, ZTITLE1 TEXT, ZSNIPPET TEXT, "
        "ZMARKEDFORDELETION INTEGER, ZTRASHEDSTATE INTEGER, ZDELETEDDATE REAL, "
        "ZCREATIONDATE REAL, ZMODIFICATIONDATE REAL, ZNOTEDATA INTEGER)"
    )
    conn.execute("CREATE TABLE ZICNOTEDATA (Z_PK INTEGER, ZDATA BLOB)")
    conn.execute(
        "INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1, "NOTE-1", "Title One", "Snippet One", 1, 0, None, 1, 1, 1),
    )
    conn.execute("INSERT INTO ZICNOTEDATA VALUES (?, ?)", (1, b"data"))
    conn.execute("INSERT INTO ZICNOTEDATA VALUES (?, ?)", (2, b"orphan"))
    conn.commit()
    conn.close()

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    query_notes(db_path, keyword="Title", out_dir=out_dir, run_ts="20260101_000000")

    assert list(out_dir.glob("icloud_snippet_search_*.csv"))
    assert list(out_dir.glob("icloud_marked_for_deletion_*.csv"))
    assert list(out_dir.glob("icloud_orphan_zicnotedata_*.csv"))
    assert list(out_dir.glob("icloud_small_zdata_*.csv"))
