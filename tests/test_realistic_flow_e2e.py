from __future__ import annotations

import datetime
import sqlite3
import struct
import zlib
from pathlib import Path

from notes_recovery.config import WAL_MAGIC_LE
from notes_recovery.services import carve, freelist, fsevents, spotlight, timeline, wal
from notes_recovery.services.query import query_notes


def _mac_absolute_seconds(dt: datetime.datetime) -> float:
    base = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)
    return (dt - base).total_seconds()


def _create_icloud_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE ZICCLOUDSYNCINGOBJECT ("
        "Z_PK INTEGER PRIMARY KEY, "
        "ZIDENTIFIER TEXT, "
        "ZTITLE1 TEXT, "
        "ZSNIPPET TEXT, "
        "ZMARKEDFORDELETION INTEGER, "
        "ZCREATIONDATE REAL, "
        "ZMODIFICATIONDATE REAL, "
        "ZNOTEDATA INTEGER)"
    )
    conn.execute(
        "CREATE TABLE ZICNOTEDATA ("
        "Z_PK INTEGER PRIMARY KEY, "
        "ZDATA BLOB)"
    )
    now = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    mac_ts = _mac_absolute_seconds(now)
    payload = zlib.compress(b"secret payload for carve")
    conn.execute(
        "INSERT INTO ZICNOTEDATA (Z_PK, ZDATA) VALUES (?, ?)",
        (1, payload),
    )
    conn.execute(
        "INSERT INTO ZICCLOUDSYNCINGOBJECT "
        "(Z_PK, ZIDENTIFIER, ZTITLE1, ZSNIPPET, ZMARKEDFORDELETION, ZCREATIONDATE, ZMODIFICATIONDATE, ZNOTEDATA) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (1, "note-1", "Title", "secret snippet", 1, mac_ts, mac_ts, 1),
    )
    conn.commit()
    conn.close()


def _append_zlib_payload(path: Path) -> None:
    payload = zlib.compress(b"secret blob for carve")
    with path.open("ab") as f:
        f.write(payload)


def _write_wal(path: Path, page_size: int, payload: bytes) -> None:
    header = struct.pack(">I", WAL_MAGIC_LE)
    header += struct.pack("<7I", 1, page_size, 0, 0, 0, 0, 0)
    frame_header = struct.pack("<6I", 1, 0, 0, 0, 0, 0)
    path.write_bytes(header + frame_header + payload)


def _create_spotlight_sqlite(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE events (note_id TEXT, created_time REAL, content TEXT)")
    conn.execute(
        "INSERT INTO events (note_id, created_time, content) VALUES (?, ?, ?)",
        ("note-1", 1700000000, "spotlight secret"),
    )
    conn.commit()
    conn.close()


def test_realistic_flow_e2e(tmp_path: Path) -> None:
    root = tmp_path / "Notes_Forensics"
    db_dir = root / "DB_Backup"
    spot_dir = root / "Spotlight_Backup"
    db_dir.mkdir(parents=True)
    spot_dir.mkdir(parents=True)

    db_path = db_dir / "NoteStore.sqlite"
    _create_icloud_db(db_path)
    _append_zlib_payload(db_path)

    wal_path = db_dir / "NoteStore.sqlite-wal"
    _write_wal(wal_path, 512, b"walpayload" * 64)

    spot_db = spot_dir / "store.db"
    _create_spotlight_sqlite(spot_db)
    (spot_dir / "queries.plist").write_bytes(
        b"<?xml version=\"1.0\"?><plist><dict><key>q</key><string>secret</string></dict></plist>"
    )

    run_ts = "20260101_000000"
    query_out = root / "Query_Output"
    query_notes(db_path, keyword="secret", out_dir=query_out, run_ts=run_ts)
    assert any(p.name.startswith("icloud_") for p in query_out.glob("*.csv"))

    carve_out = root / "Recovered_Blobs"
    carve.carve_gzip(
        db_path,
        carve_out,
        keyword="secret",
        max_hits=5,
        window_size=1024,
        min_text_len=6,
        min_text_ratio=0.2,
        algorithms=["zlib"],
    )
    assert (carve_out / "manifest.jsonl").exists()

    analysis_dir = root / "Spotlight_Analysis"
    spotlight_outputs = spotlight.parse_spotlight_deep(
        root,
        analysis_dir,
        max_files=5,
        max_bytes=1024 * 1024,
        min_string_len=3,
        max_string_chars=200,
        max_rows_per_table=50,
        run_ts=run_ts,
    )
    assert spotlight_outputs.get("spotlight_events")

    timeline_out = root / "Timeline"
    timeline_outputs = timeline.build_timeline(
        root,
        timeline_out,
        keyword="secret",
        max_notes=50,
        max_events=200,
        spotlight_max_files=5,
        include_fs=True,
        enable_plotly=False,
        run_ts=run_ts,
    )
    assert Path(timeline_outputs["timeline_json"]).exists()

    wal_out = root / "WAL_Extract"
    wal_extract_meta = wal.wal_extract(
        root_dir=root,
        out_dir=wal_out,
        keyword="secret",
        max_frames=10,
        page_size_override=512,
        dump_pages=False,
        dump_only_duplicates=False,
        strings_on=True,
        strings_min_len=4,
        strings_max_chars=200,
        run_ts=run_ts,
    )
    assert wal_extract_meta.exists()

    freelist_out = root / "Freelist_Carve"
    freelist_meta = freelist.freelist_carve(
        db_path=db_path,
        out_dir=freelist_out,
        keyword=None,
        min_text_len=6,
        max_pages=10,
        max_output_mb=1,
        max_chars=200,
        run_ts=run_ts,
    )
    assert freelist_meta.exists()

    wal_b = db_dir / "NoteStore.sqlite-wal.bak"
    wal_b.write_bytes(wal_path.read_bytes())
    diff_out = root / "WAL_Diff"
    diff_summary = wal.wal_diff(wal_path, wal_b, diff_out, max_frames=10, page_size_override=0, run_ts=run_ts)
    assert diff_summary.exists()

    fsevents_csv = root / "fsevents.csv"
    fsevents_csv.write_text(
        "timestamp,path,event\n2024-01-01T00:00:00Z,/tmp/note.txt,modify\n",
        encoding="utf-8",
    )
    fsevents_out = root / "FSEvents"
    fsevents_outputs = fsevents.correlate_fsevents_with_spotlight(
        fsevents_path=fsevents_csv,
        root_dir=root,
        spotlight_events_path=Path(spotlight_outputs["spotlight_events"]),
        out_dir=fsevents_out,
        window_seconds=60,
        max_records=100,
        run_ts=run_ts,
    )
    assert Path(fsevents_outputs["fsevents_summary"]).exists()
