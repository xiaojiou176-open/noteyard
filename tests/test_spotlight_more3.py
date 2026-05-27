from __future__ import annotations

import datetime
import plistlib
import sqlite3
from collections import Counter
from pathlib import Path

from notes_recovery.services import spotlight
from notes_recovery.models import SpotlightTokenType


def test_spotlight_timestamp_and_query_candidate() -> None:
    assert spotlight.normalize_spotlight_timestamp("bad") is None
    assert spotlight.normalize_spotlight_timestamp(-1) is None
    assert spotlight.normalize_spotlight_timestamp(1700000000) is not None
    assert spotlight.normalize_spotlight_timestamp(1700000000000) is not None
    assert spotlight.normalize_spotlight_timestamp(10) is None

    assert spotlight.is_spotlight_query_candidate("hello world") is True
    assert spotlight.is_spotlight_query_candidate("http://example.com") is False
    assert spotlight.is_spotlight_query_candidate("/tmp/path") is False
    assert spotlight.is_spotlight_query_candidate("ab") is False

    naive = spotlight.format_event_timestamp(
        datetime.datetime(2024, 1, 1, 0, 0, 0)
    )
    assert naive.endswith("Z")


def test_harvest_spotlight_tokens_and_plist(tmp_path: Path) -> None:
    counters = {t: Counter() for t in SpotlightTokenType}
    sample = "http://example.com ABCDEF12-3456-7890-ABCD-EF1234567890 /tmp/test bundle:id"
    spotlight.harvest_spotlight_tokens(sample, counters, max_matches=10)
    assert counters[SpotlightTokenType.URL]

    plist_path = tmp_path / "queries.plist"
    with plist_path.open("wb") as f:
        plistlib.dump({"q": "keyword query"}, f)
    spotlight.parse_spotlight_plist(plist_path, counters, max_matches=5)
    assert counters[SpotlightTokenType.QUERY]


def test_parse_spotlight_sqlite_and_outputs(tmp_path: Path) -> None:
    db_path = tmp_path / "store.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE events (note_id TEXT, created_time REAL, content TEXT)")
    conn.execute("INSERT INTO events VALUES (?, ?, ?)", ("note1", 1700000000, "hello spotlight"))
    conn.commit()
    conn.close()

    counters = {t: Counter() for t in SpotlightTokenType}
    tables, events = spotlight.parse_spotlight_sqlite(db_path, counters, max_matches=10, max_rows=10, max_value_chars=100)
    assert tables
    assert events

    out_dir = tmp_path / "out"
    tokens_csv = out_dir / "tokens.csv"
    events_csv = out_dir / "events.csv"
    tables_csv = out_dir / "tables.csv"
    access_csv = out_dir / "access.csv"
    diag_csv = out_dir / "diag.csv"
    spotlight.write_spotlight_tokens_csv(tokens_csv, counters, max_items=5)
    spotlight.write_spotlight_events_csv(events_csv, events)
    spotlight.write_spotlight_tables_csv(tables_csv, tables)
    spotlight.write_spotlight_access_csv(access_csv, counters, max_items=5)
    spotlight.write_spotlight_diagnostics_csv(diag_csv, [])
    assert tokens_csv.exists()
    assert events_csv.exists()
    assert tables_csv.exists()
    assert access_csv.exists()
    assert diag_csv.exists()


def test_parse_spotlight_sqlite_max_rows_zero(tmp_path: Path) -> None:
    db_path = tmp_path / "store.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE events (note_id TEXT, created_time REAL, content TEXT)")
    conn.execute("INSERT INTO events VALUES (?, ?, ?)", ("note1", 1700000000, "hello spotlight"))
    conn.commit()
    conn.close()

    counters = {t: Counter() for t in SpotlightTokenType}
    tables, events = spotlight.parse_spotlight_sqlite(db_path, counters, max_matches=10, max_rows=0, max_value_chars=50)
    assert tables
    assert events == []


def test_collect_spotlight_candidates(tmp_path: Path) -> None:
    root = tmp_path / "Spotlight_Backup"
    root.mkdir()
    db_file = root / "store.db"
    db_file.write_text("data", encoding="utf-8")
    candidates = spotlight.collect_spotlight_candidates(root, max_files=5, max_bytes=1024)
    assert db_file in candidates
    assert spotlight.collect_spotlight_candidates(root, max_files=0, max_bytes=1024) == []


def test_walk_obj_and_helpers(tmp_path: Path) -> None:
    data = {"a": [1, {"b": "c"}]}
    paths = [p for p, _v in spotlight.walk_obj(data)]
    assert "root.a[1].b" in paths

    sqlite_file = tmp_path / "db.sqlite"
    sqlite_file.write_bytes(b"SQLite format 3\x00" + b"\x00" * 20)
    assert spotlight.is_sqlite_header(sqlite_file) is True
    assert spotlight.is_sqlite_header(tmp_path / "missing.db") is False

    assert spotlight.classify_spotlight_index_type(Path("/tmp/cs_default/db")) == spotlight.SpotlightIndexType.DEFAULT
    assert spotlight.classify_spotlight_index_type(Path("/tmp/cs_priority/db")) == spotlight.SpotlightIndexType.PRIORITY
    assert spotlight.is_spotlight_deep_candidate(Path("journal.db")) is True
    assert spotlight.safe_sqlite_ident('name"with') == '"name""with"'
    assert spotlight.extract_strings_from_value(b"hello", 20)
    assert spotlight.extract_strings_from_value("world", 3) == "wor"


def test_parse_spotlight_deep_and_loaders(tmp_path: Path) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    spotlight_root = root_dir / "Spotlight_Backup"
    spotlight_root.mkdir(parents=True)

    plist_path = spotlight_root / "queries.plist"
    with plist_path.open("wb") as f:
        plistlib.dump({"query": "secret"}, f)

    sqlite_path = spotlight_root / "store.db"
    conn = sqlite3.connect(sqlite_path)
    conn.execute("CREATE TABLE events (note_id TEXT, created_time REAL, content TEXT)")
    conn.execute("INSERT INTO events VALUES (?, ?, ?)", ("note1", 1700000000, "secret"))
    conn.commit()
    conn.close()

    journal = spotlight_root / "journal.txt"
    journal.write_text("secret journal", encoding="utf-8")

    out_dir = root_dir / "Spotlight_Analysis"
    outputs = spotlight.parse_spotlight_deep(
        root_dir=root_dir,
        out_dir=out_dir,
        max_files=10,
        max_bytes=1024 * 1024,
        min_string_len=3,
        max_string_chars=200,
        max_rows_per_table=50,
        run_ts="20260101_000000",
    )
    assert Path(outputs["spotlight_metadata"]).exists()

    meta = spotlight.load_json_file(Path(outputs["spotlight_metadata"]))
    assert meta and meta.get("files_scanned", 0) >= 1

    latest = spotlight.find_latest_file(out_dir, "spotlight_*.csv")
    assert latest is not None

    assert spotlight.find_latest_spotlight_analysis_dir(root_dir) is not None
    assert spotlight.find_latest_spotlight_analysis_dir(tmp_path / "missing") is None

    bad_events = out_dir / "bad_events.csv"
    bad_events.write_text("timestamp_utc,table,column,note_id,source_path,raw_value\ninvalid\n", encoding="utf-8")
    assert spotlight.load_spotlight_events_csv(bad_events) == []
