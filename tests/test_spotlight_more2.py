from __future__ import annotations

import csv
import sqlite3
from collections import Counter
from pathlib import Path

from notes_recovery.models import SpotlightTokenType
from notes_recovery.services import spotlight


def test_parse_spotlight_sqlite_with_blob(tmp_path: Path) -> None:
    db_path = tmp_path / "spot.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE items (note_id TEXT, created INTEGER, blob BLOB)")
    conn.execute("INSERT INTO items VALUES (?, ?, ?)", ("note", 1700000000, b"http://example.com"))
    conn.commit()
    conn.close()

    counters = {token: Counter() for token in SpotlightTokenType}
    tables, events = spotlight.parse_spotlight_sqlite(db_path, counters, max_matches=10, max_rows=10, max_value_chars=200)
    assert tables
    assert counters[SpotlightTokenType.URL]

    events_csv = tmp_path / "events.csv"
    with events_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_utc", "table", "column", "note_id", "source_path", "raw_value"])
        writer.writerow(["2024-01-01T00:00:00Z", "t", "c", "note", str(db_path), "raw"])

    timeline_events = spotlight.load_spotlight_events_csv(events_csv)
    assert timeline_events
