from __future__ import annotations

from pathlib import Path

from notes_recovery.models import WalAction
from notes_recovery.services import wal


def test_wal_isolate_copy_restore(tmp_path: Path) -> None:
    target = tmp_path / "DB_Backup"
    target.mkdir()
    wal_path = target / "NoteStore.sqlite-wal"
    shm_path = target / "NoteStore.sqlite-shm"
    wal_path.write_text("wal", encoding="utf-8")
    shm_path.write_text("shm", encoding="utf-8")

    wal.wal_isolate(target, WalAction.COPY_ONLY, "WAL_Isolation", allow_original=True)
    iso_dir = target / "WAL_Isolation"
    assert (iso_dir / wal_path.name).exists()

    wal.wal_isolate(target, WalAction.ISOLATE, "WAL_Isolation", allow_original=True)
    assert not wal_path.exists()

    wal.wal_isolate(target, WalAction.RESTORE, "WAL_Isolation", allow_original=True)
    assert wal_path.exists()
