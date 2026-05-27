from __future__ import annotations

import plistlib
import sqlite3
from pathlib import Path

from notes_recovery.services import spotlight


def _write_spotlight_sqlite(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE events (note_id TEXT, ts INTEGER, info TEXT)")
    conn.execute("INSERT INTO events VALUES (?, ?, ?)", ("note1", 1700000000, "hello"))
    conn.commit()
    conn.close()


def test_safe_sqlite_ident_escapes_embedded_quotes() -> None:
    assert spotlight.safe_sqlite_ident('notes"name') == '"notes""name"'


def test_parse_spotlight_deep(tmp_path: Path) -> None:
    root = tmp_path / "root"
    spot = root / "Spotlight_Backup"
    spot.mkdir(parents=True)

    with (spot / "test.plist").open("wb") as f:
        plistlib.dump({"query": "hello"}, f)

    _write_spotlight_sqlite(spot / "store.db")
    (spot / "journal.txt").write_text("com.apple.notes.table hello", encoding="utf-8")

    out_dir = tmp_path / "out"
    outputs = spotlight.parse_spotlight_deep(
        root_dir=root,
        out_dir=out_dir,
        max_files=10,
        max_bytes=1024 * 1024,
        min_string_len=3,
        max_string_chars=2000,
        max_rows_per_table=100,
        run_ts="20260101_000000",
    )
    assert outputs
    assert Path(outputs["spotlight_metadata"]).exists()
    assert Path(outputs["spotlight_events"]).exists()
