from __future__ import annotations

from pathlib import Path

import notes_recovery.services.recover as recover


def test_recover_notes_with_deep_scan(tmp_path: Path) -> None:
    root = tmp_path / "root"
    db_dir = root / "DB_Backup"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "NoteStore.sqlite"
    db_path.write_bytes(b"xxxxsecretxxxx")

    out_dir = tmp_path / "recover"
    recover.recover_notes_by_keyword(
        root_dir=root,
        keyword="secret",
        out_dir=out_dir,
        min_overlap=3,
        max_fragments=10,
        max_stitch_rounds=2,
        include_deep=True,
        deep_all=False,
        deep_max_mb=1,
        deep_max_hits_per_file=5,
        match_all=False,
        binary_copy=True,
        binary_copy_max_mb=1,
        run_ts="20260101_000000",
    )

    binary_dir = out_dir / "Binary_Hits"
    assert binary_dir.exists()
    assert list(binary_dir.glob("binary_hits_*.csv"))
