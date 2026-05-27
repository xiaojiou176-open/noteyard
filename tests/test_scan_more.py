from __future__ import annotations

import os
from pathlib import Path

from notes_recovery.core import scan


def test_collect_deep_scan_targets(tmp_path: Path) -> None:
    root = tmp_path / "root"
    db_dir = root / "DB_Backup"
    cache_dir = root / "Cache_Backup"
    spot_dir = root / "Spotlight_Backup"
    recovered = root / "Recovered_DB"
    wal_iso = db_dir / "WAL_Isolation"
    for d in (db_dir, cache_dir, spot_dir, recovered, wal_iso):
        d.mkdir(parents=True, exist_ok=True)

    (db_dir / "NoteStore.sqlite").write_text("db", encoding="utf-8")
    (db_dir / "NoteStore.sqlite-wal").write_text("wal", encoding="utf-8")
    (db_dir / "NoteStore.sqlite-shm").write_text("shm", encoding="utf-8")
    (wal_iso / "extra.sqlite-wal").write_text("wal", encoding="utf-8")
    (wal_iso / "extra.sqlite-shm").write_text("shm", encoding="utf-8")

    (recovered / "recovered.sqlite").write_text("db", encoding="utf-8")
    sym = recovered / "skip.sqlite"
    try:
        os.symlink(recovered / "recovered.sqlite", sym)
    except OSError:
        pass

    (cache_dir / "NotesV7.storedata").write_text("cache", encoding="utf-8")
    cache_sym = cache_dir / "NotesV7.storedata-wal"
    try:
        os.symlink(cache_dir / "NotesV7.storedata", cache_sym)
    except OSError:
        cache_sym.write_text("wal", encoding="utf-8")

    (spot_dir / "store.db").write_text("db", encoding="utf-8")
    (spot_dir / ".store.db").write_text("db", encoding="utf-8")
    (spot_dir / "note.txt").write_text("txt", encoding="utf-8")

    targets = scan.collect_deep_scan_targets(root)
    assert any("NoteStore.sqlite" in str(p) for p in targets)
    assert any("store.db" in str(p) for p in targets)


def test_collect_deep_scan_targets_extended_and_helpers(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "DB_Backup").mkdir(parents=True)
    skip = root / "Recovered_Notes"
    skip.mkdir()
    (skip / "skip.txt").write_text("skip", encoding="utf-8")
    bundle = root / "Text_Bundle_1"
    bundle.mkdir()
    (bundle / "bundle.txt").write_text("bundle", encoding="utf-8")
    (root / "DB_Backup" / "file.bin").write_text("bin", encoding="utf-8")

    extended = scan.collect_deep_scan_targets_extended(root)
    assert any(p.name == "file.bin" for p in extended)
    assert not any("Recovered_Notes" in str(p) for p in extended)
    assert not any("Text_Bundle" in str(p) for p in extended)

    dirs = scan.collect_prefixed_dirs(root, "DB_Backup")
    assert dirs

    assert scan.should_skip_recovery_path(bundle / "bundle.txt")
    assert scan.should_skip_recovery_path(skip / "skip.txt")
