from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path

from notes_recovery.services import timeline


def _create_icloud_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE ZICCLOUDSYNCINGOBJECT ("
        "Z_PK INTEGER PRIMARY KEY, "
        "ZIDENTIFIER TEXT, "
        "ZTITLE1 TEXT, "
        "ZSNIPPET TEXT, "
        "ZMARKEDFORDELETION INTEGER, "
        "ZCREATIONDATE REAL, "
        "ZDELETEDDATE REAL)"
    )
    conn.execute(
        "INSERT INTO ZICCLOUDSYNCINGOBJECT (Z_PK, ZIDENTIFIER, ZTITLE1, ZSNIPPET, ZMARKEDFORDELETION, ZCREATIONDATE, ZDELETEDDATE) "
        "VALUES (1, 'note-1', 'Title', 'Snippet', 1, 1000, NULL)"
    )
    conn.commit()
    conn.close()


def test_timeline_timestamp_and_keyword_where() -> None:
    assert timeline.mac_absolute_to_datetime(1e20) is None
    assert timeline.unix_to_datetime("bad") is None
    ts = timeline.format_event_timestamp(datetime.datetime(2024, 1, 1, 0, 0, 0))
    assert ts.endswith("Z")
    clause, params = timeline.build_keyword_where("t", [], "hello")
    assert clause == "" and params == []


def test_extract_db_events_icloud_branches(tmp_path: Path) -> None:
    db_path = tmp_path / "note.sqlite"
    _create_icloud_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # keyword miss branch
    events = timeline.extract_db_events_icloud(conn, keyword="miss", max_notes=10)
    assert events == []

    # include events & marked deleted branch
    events = timeline.extract_db_events_icloud(conn, keyword=None, max_notes=10)
    assert events
    conn.close()


def _create_legacy_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE ZNOTE (Z_PK INTEGER PRIMARY KEY, ZTITLE TEXT, ZMODIFICATIONDATE REAL)"
    )
    conn.execute(
        "CREATE TABLE ZNOTEBODY (ZNOTE INTEGER, ZHTMLSTRING TEXT)"
    )
    conn.execute("INSERT INTO ZNOTE VALUES (1, 'Legacy', 1000)")
    conn.execute("INSERT INTO ZNOTEBODY VALUES (1, '<p>Legacy body</p>')")
    conn.commit()
    conn.close()


def test_extract_db_events_legacy_branches(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.sqlite"
    _create_legacy_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    events = timeline.extract_db_events_legacy(conn, keyword="miss", max_notes=10)
    assert events == []

    events = timeline.extract_db_events_legacy(conn, keyword=None, max_notes=10)
    assert events
    conn.close()
