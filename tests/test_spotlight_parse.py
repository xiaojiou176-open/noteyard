import sqlite3
from collections import Counter
from pathlib import Path

from notes_recovery.models import SpotlightTokenType
from notes_recovery.services.spotlight import parse_spotlight_sqlite


def test_parse_spotlight_sqlite_basic(tmp_path: Path) -> None:
    db_path = tmp_path / "spotlight.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE items (id INTEGER, note_id TEXT, title TEXT, created REAL)")
        conn.execute(
            "INSERT INTO items VALUES (?, ?, ?, ?)",
            (1, "NOTE-UUID-1234", "hello https://example.com", 1700000000.0),
        )
        conn.commit()
    finally:
        conn.close()

    counters = {token: Counter() for token in SpotlightTokenType}
    tables, events = parse_spotlight_sqlite(
        db_path,
        counters,
        max_matches=10,
        max_rows=10,
        max_value_chars=200,
    )

    assert any(row[1] == "items" for row in tables)
    assert counters[SpotlightTokenType.URL]
    assert events
