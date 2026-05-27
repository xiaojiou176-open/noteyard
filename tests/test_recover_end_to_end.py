from __future__ import annotations

from pathlib import Path

from notes_recovery.services import recover


def test_recover_notes_by_keyword_end_to_end(tmp_path: Path) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    blob_dir = root_dir / "Recovered_Blobs"
    query_dir = root_dir / "Query_Output"
    plugin_dir = root_dir / "Plugins_Output" / "tool"
    db_dir = root_dir / "DB_Backup"
    cache_dir = root_dir / "Cache_Backup"
    blob_dir.mkdir(parents=True)
    query_dir.mkdir(parents=True)
    plugin_dir.mkdir(parents=True)
    db_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)

    (blob_dir / "frag.txt").write_text("secret fragment", encoding="utf-8")
    (query_dir / "hits.csv").write_text("col\nsecret row\n", encoding="utf-8")
    (plugin_dir / "plugin.log").write_text("secret plugin", encoding="utf-8")
    (db_dir / "NoteStore.sqlite").write_bytes(b"secret binary" + "secret".encode("utf-16le"))
    (cache_dir / "NotesV7.storedata").write_bytes(b"secret cache")

    out_dir = tmp_path / "Recovered_Notes"
    recover.recover_notes_by_keyword(
        root_dir=root_dir,
        keyword="secret",
        out_dir=out_dir,
        min_overlap=3,
        max_fragments=20,
        max_stitch_rounds=50,
        include_deep=True,
        deep_all=True,
        deep_max_mb=1,
        deep_max_hits_per_file=20,
        match_all=False,
        binary_copy=True,
        binary_copy_max_mb=1,
        run_ts="20260101_000000",
    )

    assert (out_dir / "Fragments").exists()
    assert (out_dir / "Stitched").exists()
    assert (out_dir / "Meta").exists()
