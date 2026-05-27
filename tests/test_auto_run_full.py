from __future__ import annotations

import plistlib
from pathlib import Path

import notes_recovery.config as config
from notes_recovery.models import DefaultPaths
from notes_recovery.services.auto import auto_run


def _write_spotlight_sqlite(path: Path) -> None:
    import sqlite3
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE events (note_id TEXT, ts INTEGER, info TEXT)")
    conn.execute("INSERT INTO events VALUES (?, ?, ?)", ("note1", 1700000000, "Title keyword"))
    conn.commit()
    conn.close()


def test_auto_run_full_pipeline(tmp_path: Path, monkeypatch) -> None:
    orig_root = tmp_path / "orig"
    notes_container = orig_root / "notes"
    spotlight = orig_root / "spotlight"
    cache = orig_root / "cache"
    notes_container.mkdir(parents=True)
    spotlight.mkdir(parents=True)
    cache.mkdir(parents=True)

    source_db = Path(__file__).parent / "data" / "icloud_min.sqlite"
    (notes_container / "NoteStore.sqlite").write_bytes(source_db.read_bytes())
    (notes_container / "NoteStore.sqlite-wal").write_bytes(b"wal")
    (notes_container / "NoteStore.sqlite-shm").write_bytes(b"shm")

    plist_path = spotlight / "test.plist"
    with plist_path.open("wb") as f:
        plistlib.dump({"query": "Title keyword"}, f)
    sqlite_path = spotlight / "store.db"
    _write_spotlight_sqlite(sqlite_path)

    (cache / "NotesV7.storedata").write_text("Title keyword", encoding="utf-8")

    fake_paths = DefaultPaths(
        notes_group_container=notes_container,
        core_spotlight=spotlight,
        notes_cache=cache,
    )
    monkeypatch.setattr(config, "DEFAULT_PATHS", fake_paths)
    import notes_recovery.services.snapshot as snapshot_service
    import notes_recovery.services.wal as wal_service
    monkeypatch.setattr(snapshot_service, "DEFAULT_PATHS", fake_paths)
    monkeypatch.setattr(wal_service, "DEFAULT_PATHS", fake_paths)

    plugins_config = tmp_path / "plugins.json"
    plugins_config.write_text(
        "{"
        "\"tools\": ["
        "{\"name\": \"echo\", \"command\": [\"/bin/echo\", \"ok\"], \"enabled\": true, \"output_dir\": \"Plugins_Output/echo\"}"
        "]}"
    )

    out_dir = tmp_path / "case"
    run_ts = "20260102_000000"

    auto_run(
        out_dir=out_dir,
        keyword="Title",
        include_core_spotlight=True,
        include_notes_cache=True,
        run_wal=True,
        run_query=True,
        run_carve=True,
        run_recover=True,
        recover_ignore_freelist=False,
        recover_lost_and_found="lost_and_found",
        run_plugins_flag=True,
        plugins_config=plugins_config,
        plugins_enable_all=False,
        generate_html_report=True,
        report_out=None,
        report_max_items=20,
        carve_max_hits=5,
        carve_window_size=1024,
        carve_min_text_len=8,
        carve_min_text_ratio=0.3,
        run_protobuf=True,
        protobuf_max_notes=10,
        protobuf_max_zdata_mb=1,
        run_spotlight_parse=True,
        spotlight_parse_max_files=10,
        spotlight_parse_max_bytes=1024 * 1024,
        spotlight_parse_min_string_len=3,
        spotlight_parse_max_string_chars=2000,
        spotlight_parse_max_rows=200,
        run_verify=False,
        verify_top_n=5,
        verify_preview_len=120,
        verify_out=None,
        verify_deep=True,
        verify_deep_max_mb=1,
        verify_deep_max_hits_per_file=50,
        verify_deep_all=True,
        verify_match_all=False,
        verify_fuzzy=True,
        verify_fuzzy_threshold=0.5,
        verify_fuzzy_boost=2.0,
        verify_fuzzy_max_len=500,
        run_ts_override=run_ts,
    )

    root_dir = out_dir.parent / f"{out_dir.name}_{run_ts}"
    assert (root_dir / "Recovered_DB").exists()
    assert (root_dir / "Protobuf_Output").exists()
    assert (root_dir / "Plugins_Output").exists()
    assert (root_dir / "review_index.md").exists()
