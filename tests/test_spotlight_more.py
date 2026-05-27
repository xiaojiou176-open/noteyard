import csv
import sqlite3
from pathlib import Path
from collections import Counter

from notes_recovery.models import SpotlightTokenType
from notes_recovery.services import spotlight


def test_spotlight_helpers(tmp_path: Path) -> None:
    assert spotlight.is_spotlight_query_candidate("hello world")
    assert not spotlight.is_spotlight_query_candidate("ab")
    assert spotlight.normalize_spotlight_timestamp(1700000000) is not None
    assert spotlight.normalize_spotlight_timestamp(0) is None

    counters = {
        SpotlightTokenType.QUERY: Counter(),
        SpotlightTokenType.BUNDLE_ID: Counter(),
        SpotlightTokenType.FILE_PATH: Counter(),
        SpotlightTokenType.URL: Counter(),
        SpotlightTokenType.NOTE_ID: Counter(),
    }
    text = "https://example.com com.apple.notes.table /tmp/test/file.txt 123e4567-e89b-12d3-a456-426614174000"\
           "\nmy search query"
    spotlight.harvest_spotlight_tokens(text, counters, max_matches=10)
    assert counters[SpotlightTokenType.URL]
    assert counters[SpotlightTokenType.BUNDLE_ID]


def test_parse_spotlight_sqlite_and_events(tmp_path: Path) -> None:
    db_path = tmp_path / "spot.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE events (note_id TEXT, created INTEGER, info TEXT)")
    conn.execute("INSERT INTO events VALUES (?, ?, ?)", ("note", 1700000000, "Hello"))
    conn.commit()
    conn.close()

    counters = {
        SpotlightTokenType.QUERY: Counter(),
        SpotlightTokenType.BUNDLE_ID: Counter(),
        SpotlightTokenType.FILE_PATH: Counter(),
        SpotlightTokenType.URL: Counter(),
        SpotlightTokenType.NOTE_ID: Counter(),
    }
    tables, events = spotlight.parse_spotlight_sqlite(db_path, counters, max_matches=50, max_rows=10, max_value_chars=200)
    assert tables
    assert events

    events_csv = tmp_path / "events.csv"
    with events_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_utc", "table", "column", "note_id", "source_path", "raw_value"])
        writer.writerow(["2024-01-01T00:00:00Z", "t", "c", "note", str(db_path), "raw"])

    timeline_events = spotlight.load_spotlight_events_csv(events_csv)
    assert timeline_events
