from __future__ import annotations

import json
from pathlib import Path

from notes_recovery.services import fsevents


def test_parse_fsevents_csv_and_json(tmp_path: Path) -> None:
    csv_path = tmp_path / "events.csv"
    csv_path.write_text("timestamp,path,event\n2024-01-01T00:00:00Z,/tmp/a.txt,modify\n", encoding="utf-8")
    records = fsevents.load_fsevents_records(csv_path, max_records=10)
    assert records

    json_path = tmp_path / "events.json"
    json_path.write_text(json.dumps({"events": [{"timestamp": 1700000000, "path": "/tmp/b.txt"}]}), encoding="utf-8")
    records = fsevents.load_fsevents_records(json_path, max_records=10)
    assert records

    jsonl_path = tmp_path / "events.jsonl"
    jsonl_path.write_text('{"timestamp": "2024-01-01T00:00:01Z", "path": "/tmp/c.txt"}\n', encoding="utf-8")
    records = fsevents.load_fsevents_records(jsonl_path, max_records=10)
    assert records


def test_correlate_fsevents_with_spotlight(tmp_path: Path) -> None:
    fsevents_path = tmp_path / "events.csv"
    fsevents_path.write_text(
        "timestamp,path,event\n2024-01-01T00:00:00Z,/tmp/note.txt,modify\n",
        encoding="utf-8",
    )
    spotlight_events = tmp_path / "spotlight_events.csv"
    spotlight_events.write_text(
        "timestamp_utc,table,column,note_id,source_path,raw_value\n"
        "2024-01-01T00:00:01Z,events,created_time,N1,/tmp/note.txt,hello\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    outputs = fsevents.correlate_fsevents_with_spotlight(
        fsevents_path=fsevents_path,
        root_dir=None,
        spotlight_events_path=spotlight_events,
        out_dir=out_dir,
        window_seconds=10,
        max_records=100,
        run_ts="20260101_000000",
    )
    assert Path(outputs["fsevents_matches"]).exists()
    assert Path(outputs["fsevents_summary"]).exists()
