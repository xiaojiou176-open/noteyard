from pathlib import Path

from notes_recovery.services.wal import wal_isolate
from notes_recovery.models import WalAction


def test_wal_isolate_and_restore(tmp_path: Path) -> None:
    wal = tmp_path / "NoteStore.sqlite-wal"
    shm = tmp_path / "NoteStore.sqlite-shm"
    wal.write_bytes(b"wal")
    shm.write_bytes(b"shm")

    wal_isolate(tmp_path, WalAction.ISOLATE, "WAL_Isolation", allow_original=True)
    isolate_dir = tmp_path / "WAL_Isolation"
    assert (isolate_dir / wal.name).exists()
    assert (isolate_dir / shm.name).exists()
    assert not wal.exists()
    assert not shm.exists()

    wal_isolate(tmp_path, WalAction.RESTORE, "WAL_Isolation", allow_original=True)
    assert wal.exists()
    assert shm.exists()
