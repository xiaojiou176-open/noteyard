from __future__ import annotations

from pathlib import Path

from notes_recovery.services import verify


def test_verify_hits_with_deep_scan(tmp_path: Path) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    query_dir = root_dir / "Query_Output"
    blob_dir = root_dir / "Recovered_Blobs"
    db_dir = root_dir / "DB_Backup"
    query_dir.mkdir(parents=True)
    blob_dir.mkdir(parents=True)
    db_dir.mkdir(parents=True)

    query_csv = query_dir / "query.csv"
    query_csv.write_text("col\nsecret hit\n", encoding="utf-8")

    blob_txt = blob_dir / "blob.txt"
    blob_txt.write_text("secret blob", encoding="utf-8")

    binary_path = db_dir / "NoteStore.sqlite"
    binary_path.write_bytes(b"secret binary" + "secret".encode("utf-16le"))

    out_dir = root_dir / "Verification"
    verify.verify_hits(
        root_dir=root_dir,
        keyword="secret",
        top_n=5,
        preview_len=120,
        out_dir=out_dir,
        deep=True,
        deep_max_mb=1,
        deep_max_hits_per_file=10,
        match_all=False,
        fuzzy=False,
        fuzzy_threshold=0.5,
        fuzzy_boost=1.0,
        fuzzy_max_len=200,
        run_ts="20260101_000000",
        deep_all=True,
    )
    assert (out_dir / "verify_hits_20260101_000000.csv").exists()
