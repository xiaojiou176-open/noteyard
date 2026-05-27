from __future__ import annotations

import datetime
import json
from pathlib import Path

from notes_recovery.services import fsevents


def test_parse_fsevents_timestamp_variants() -> None:
    ts_int = fsevents.parse_fsevents_timestamp(1700000000)
    assert ts_int is not None
    assert ts_int.tzinfo is not None

    ts_ms = fsevents.parse_fsevents_timestamp("1700000000000")
    assert ts_ms is not None

    ts_iso = fsevents.parse_fsevents_timestamp("2024-01-01T00:00:00Z")
    assert ts_iso == datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)

    assert fsevents.parse_fsevents_timestamp("bad") is None
    assert fsevents.parse_fsevents_timestamp(-1) is None


def test_parse_fsevents_json_payload_variants(tmp_path: Path) -> None:
    json_events = tmp_path / "events.json"
    json_events.write_text(
        json.dumps({"events": [{"timestamp": 1700000000, "path": "/tmp/a"}]}),
        encoding="utf-8",
    )
    records = fsevents.parse_fsevents_json(json_events, max_records=10)
    assert records and records[0]["path"] == "/tmp/a"

    json_single = tmp_path / "single.json"
    json_single.write_text(
        json.dumps({"timestamp": "2024-01-01T00:00:00Z", "path": "/tmp/b", "event": "modify"}),
        encoding="utf-8",
    )
    records = fsevents.parse_fsevents_json(json_single, max_records=10)
    assert records and records[0]["event"] == "modify"

    json_list = tmp_path / "list.json"
    json_list.write_text(
        json.dumps([{"timestamp": 1700000001, "path": "/tmp/c"}]),
        encoding="utf-8",
    )
    records = fsevents.parse_fsevents_json(json_list, max_records=10)
    assert records and records[0]["path"] == "/tmp/c"

    jsonl = tmp_path / "events.jsonl"
    jsonl.write_text(
        "{\"timestamp\": 1700000002, \"path\": \"/tmp/d\"}\n"
        "not-json\n"
        "{\"timestamp\": 1700000003, \"path\": \"/tmp/e\", \"event\": \"rename\"}\n",
        encoding="utf-8",
    )
    records = fsevents.parse_fsevents_json(jsonl, max_records=10)
    assert len(records) == 2
    assert records[1]["event"] == "rename"


def test_correlate_fsevents_with_spotlight_auto_detect(tmp_path: Path) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    analysis_dir = root_dir / "Spotlight_Analysis_20260101"
    analysis_dir.mkdir(parents=True)

    events_csv = analysis_dir / "spotlight_events_20260101.csv"
    events_csv.write_text(
        "timestamp_utc,table,column,note_id,source_path,raw_value\n"
        "2024-01-01T00:00:10Z,events,created_time,N1,/tmp/note.txt,raw\n",
        encoding="utf-8",
    )

    fsevents_jsonl = root_dir / "events.jsonl"
    fsevents_jsonl.write_text(
        "{\"timestamp\": \"2024-01-01T00:00:05Z\", \"path\": \"/tmp/note.txt\", \"event\": \"modify\"}\n",
        encoding="utf-8",
    )

    out_dir = root_dir / "FSEvents"
    outputs = fsevents.correlate_fsevents_with_spotlight(
        fsevents_path=fsevents_jsonl,
        root_dir=root_dir,
        spotlight_events_path=None,
        out_dir=out_dir,
        window_seconds=10,
        max_records=100,
        run_ts="20260101_000000",
    )
    assert Path(outputs["fsevents_matches"]).exists()
    assert Path(outputs["fsevents_unmatched"]).exists()
    assert Path(outputs["fsevents_summary"]).exists()
