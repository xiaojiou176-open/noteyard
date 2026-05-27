from __future__ import annotations

import sqlite3
from pathlib import Path

from notes_recovery.services import timeline
from notes_recovery.models import TimelineEventType


def _write_legacy_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE ZNOTE (Z_PK INTEGER, ZTITLE TEXT, ZDATEEDITED REAL, ZCREATIONDATE REAL, ZMODIFICATIONDATE REAL)")
    conn.execute("CREATE TABLE ZNOTEBODY (Z_PK INTEGER, ZNOTE INTEGER, ZHTMLSTRING TEXT)")
    conn.execute("INSERT INTO ZNOTE VALUES (1, 'Legacy', 1700000000, 1700000000, 1700000000)")
    conn.execute("INSERT INTO ZNOTEBODY VALUES (1, 1, '<b>hello</b>')")
    conn.commit()
    conn.close()


def test_extract_db_events_icloud_and_legacy(tmp_path: Path) -> None:
    # iCloud DB
    icloud_db = tmp_path / "icloud.sqlite"
    conn = sqlite3.connect(icloud_db)
    conn.execute(
        "CREATE TABLE ZICCLOUDSYNCINGOBJECT ("
        "Z_PK INTEGER, ZIDENTIFIER TEXT, ZTITLE1 TEXT, ZSNIPPET TEXT, "
        "ZCREATIONDATE REAL, ZMODIFICATIONDATE REAL, ZDELETEDDATE REAL, "
        "ZMARKEDFORDELETION INTEGER, ZLASTOPENEDDATE REAL, ZLASTVIEWEDMODIFICATIONDATE REAL, "
        "ZNOTEDATA INTEGER)"
    )
    conn.execute("CREATE TABLE ZICNOTEDATA (Z_PK INTEGER, ZDATA BLOB)")
    conn.execute(
        "INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1, "NOTE-1", "Title", "Snippet", 1700000000, 1700000000, None, 0, None, None, 1),
    )
    conn.execute("INSERT INTO ZICNOTEDATA VALUES (?, ?)", (1, b"data"))
    conn.commit()
    conn.row_factory = sqlite3.Row
    try:
        events = timeline.extract_db_events_icloud(conn, keyword=None, max_notes=20)
    finally:
        conn.close()
    assert events

    legacy_db = tmp_path / "legacy.sqlite"
    _write_legacy_db(legacy_db)
    legacy_conn = sqlite3.connect(legacy_db)
    legacy_conn.row_factory = sqlite3.Row
    try:
        legacy_events = timeline.extract_db_events_legacy(legacy_conn, keyword="Legacy", max_notes=20)
    finally:
        legacy_conn.close()
    assert legacy_events


def test_extract_fs_events(tmp_path: Path) -> None:
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello", encoding="utf-8")
    events = timeline.extract_fs_events([file_path])
    assert events
    assert events[0].source_detail


def test_extract_db_events_marked_deleted(tmp_path: Path) -> None:
    db_path = tmp_path / "icloud.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE ZICCLOUDSYNCINGOBJECT ("
        "Z_PK INTEGER, ZIDENTIFIER TEXT, ZTITLE1 TEXT, ZSNIPPET TEXT, "
        "ZCREATIONDATE REAL, ZMODIFICATIONDATE REAL, ZDELETEDDATE REAL, "
        "ZMARKEDFORDELETION INTEGER, ZLASTOPENEDDATE REAL, ZLASTVIEWEDMODIFICATIONDATE REAL)"
    )
    conn.execute(
        "INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1, "NOTE-DEL", "Title", "Snippet", 100000.0, 100000.0, None, 1, None, None),
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    try:
        events = timeline.extract_db_events_icloud(conn, keyword=None, max_notes=10)
    finally:
        conn.close()

    assert any(e.event_type == TimelineEventType.MARKED_DELETED for e in events)


def test_extract_db_events_legacy_creation_only(tmp_path: Path) -> None:
    legacy_db = tmp_path / "legacy_creation.sqlite"
    conn = sqlite3.connect(legacy_db)
    conn.execute("CREATE TABLE ZNOTE (Z_PK INTEGER, ZTITLE TEXT, ZCREATIONDATE REAL)")
    conn.execute("CREATE TABLE ZNOTEBODY (Z_PK INTEGER, ZNOTE INTEGER, ZHTMLSTRING TEXT)")
    conn.execute("INSERT INTO ZNOTE VALUES (1, 'Legacy', 1700000000)")
    conn.execute("INSERT INTO ZNOTEBODY VALUES (1, 1, '<b>body</b>')")
    conn.commit()
    conn.row_factory = sqlite3.Row
    try:
        events = timeline.extract_db_events_legacy(conn, keyword=None, max_notes=10)
    finally:
        conn.close()
    assert events
