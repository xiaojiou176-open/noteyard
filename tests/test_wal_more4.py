from __future__ import annotations

import struct
from pathlib import Path

import pytest

from notes_recovery.config import WAL_MAGIC_LE
from notes_recovery.models import DefaultPaths, WalAction
from notes_recovery.services import wal


def _write_wal(path: Path, page_size: int, payload: bytes) -> None:
    header = struct.pack(">I", WAL_MAGIC_LE)
    header += struct.pack("<7I", 1, page_size, 0, 0, 0, 0, 0)
    frame_header = struct.pack("<6I", 1, 0, 0, 0, 0, 0)
    path.write_bytes(header + frame_header + payload)


def test_wal_isolate_copy_isolate_restore(tmp_path: Path) -> None:
    db_dir = tmp_path / "DB_Backup"
    db_dir.mkdir()
    wal_path = db_dir / "NoteStore.sqlite-wal"
    shm_path = db_dir / "NoteStore.sqlite-shm"
    wal_path.write_text("wal", encoding="utf-8")
    shm_path.write_text("shm", encoding="utf-8")

    wal.wal_isolate(db_dir, WalAction.COPY_ONLY, "WAL_Isolation", allow_original=True)
    isolate_dir = db_dir / "WAL_Isolation"
    assert (isolate_dir / wal_path.name).exists()
    assert wal_path.exists()

    wal.wal_isolate(db_dir, WalAction.ISOLATE, "WAL_Isolation", allow_original=True)
    assert not wal_path.exists()
    assert (isolate_dir / wal_path.name).exists()

    wal.wal_isolate(db_dir, WalAction.RESTORE, "WAL_Isolation", allow_original=True)
    assert wal_path.exists()


def test_wal_isolate_rejects_original(monkeypatch, tmp_path: Path) -> None:
    db_dir = tmp_path / "DB_Backup"
    db_dir.mkdir()
    monkeypatch.setattr(
        wal,
        "DEFAULT_PATHS",
        DefaultPaths(
            notes_group_container=tmp_path,
            core_spotlight=tmp_path,
            notes_cache=tmp_path,
        ),
    )
    with pytest.raises(RuntimeError):
        wal.wal_isolate(db_dir, WalAction.ISOLATE, "WAL_Isolation", allow_original=False)


def test_wal_isolate_unknown_action(tmp_path: Path) -> None:
    db_dir = tmp_path / "DB_Backup"
    db_dir.mkdir()
    with pytest.raises(RuntimeError):
        wal.wal_isolate(db_dir, "bad", "WAL_Isolation", allow_original=True)  # type: ignore[arg-type]


def test_wal_extract_missing_files(tmp_path: Path) -> None:
    root = tmp_path / "root"
    out_dir = tmp_path / "out"
    root.mkdir()
    out_dir.mkdir()
    with pytest.raises(RuntimeError):
        wal.wal_extract(
            root_dir=root,
            out_dir=out_dir,
            keyword=None,
            max_frames=10,
            page_size_override=0,
            dump_pages=False,
            dump_only_duplicates=False,
            strings_on=False,
            strings_min_len=4,
            strings_max_chars=200,
            run_ts="20260101_000000",
        )


def test_wal_extract_skips_missing_wal(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "root"
    out_dir = tmp_path / "out"
    root.mkdir()
    out_dir.mkdir()
    missing = tmp_path / "missing.wal"
    warns: list[str] = []
    monkeypatch.setattr(wal, "log_warn", lambda msg: warns.append(msg))

    meta = wal.wal_extract(
        root_dir=root,
        out_dir=out_dir,
        keyword=None,
        max_frames=5,
        page_size_override=0,
        dump_pages=False,
        dump_only_duplicates=False,
        strings_on=False,
        strings_min_len=4,
        strings_max_chars=200,
        run_ts="20260101_000000",
        wal_path=missing,
    )
    assert meta.exists()
    assert warns


def test_wal_extract_basic_outputs(tmp_path: Path) -> None:
    root = tmp_path / "root"
    out_dir = tmp_path / "out"
    root.mkdir()
    out_dir.mkdir()
    wal_path = tmp_path / "test.wal"
    payload = (b"hello world " * 50)[:512]
    _write_wal(wal_path, page_size=512, payload=payload)

    meta = wal.wal_extract(
        root_dir=root,
        out_dir=out_dir,
        keyword=None,
        max_frames=1,
        page_size_override=512,
        dump_pages=True,
        dump_only_duplicates=False,
        strings_on=True,
        strings_min_len=4,
        strings_max_chars=200,
        run_ts="20260101_000000",
        wal_path=wal_path,
    )
    assert meta.exists()
    wal_dir = out_dir / wal.sanitize_label(wal_path.name)
    assert (wal_dir / "wal_header.json").exists()
    assert (wal_dir / "Pages").exists()
    assert (wal_dir / "Strings").exists()
