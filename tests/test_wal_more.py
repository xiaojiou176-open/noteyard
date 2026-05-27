from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from notes_recovery.config import WAL_MAGIC_LE
from notes_recovery.services import wal
from notes_recovery.models import WalAction


def _build_wal(path: Path, page_size: int, frames: list[tuple[int, bytes]]) -> None:
    header = struct.pack(">I", WAL_MAGIC_LE)
    header += struct.pack("<7I", 1, page_size, 0, 0, 0, 0, 0)
    payloads = [header]
    for page_no, data in frames:
        frame_header = struct.pack("<6I", page_no, 0, 0, 0, 0, 0)
        payload = data.ljust(page_size, b"\x00")[:page_size]
        payloads.append(frame_header + payload)
    path.write_bytes(b"".join(payloads))


def test_parse_wal_header_invalid_magic(tmp_path: Path) -> None:
    wal_path = tmp_path / "bad.wal"
    wal_path.write_bytes(b"BAD!" + b"\x00" * 64)
    with pytest.raises(RuntimeError):
        wal.parse_wal_header(wal_path, page_size_override=0)


def test_parse_wal_header_override(tmp_path: Path) -> None:
    wal_path = tmp_path / "override.wal"
    _build_wal(wal_path, page_size=512, frames=[(1, b"hello")])
    header = wal.parse_wal_header(wal_path, page_size_override=1024)
    assert header["page_size"] == 1024


def test_wal_frame_iteration_and_trailing(tmp_path: Path) -> None:
    wal_path = tmp_path / "sample.wal"
    _build_wal(wal_path, page_size=512, frames=[(1, b"alpha"), (2, b"beta")])
    wal_path.write_bytes(wal_path.read_bytes() + b"trail")
    header = wal.parse_wal_header(wal_path, page_size_override=0)
    endian = ">" if header["endian"] == "big" else "<"
    counts, frame_count, trailing = wal.count_wal_page_occurrences(wal_path, 512, endian, max_frames=10)
    assert frame_count == 2
    assert trailing > 0
    frames = list(wal.iter_wal_frames(wal_path, 512, endian, max_frames=10))
    assert frames and frames[0]["page_no"] == 1


def test_wal_isolate_copy_restore(tmp_path: Path) -> None:
    db_dir = tmp_path / "DB_Backup"
    db_dir.mkdir()
    wal_path = db_dir / "NoteStore.sqlite-wal"
    shm_path = db_dir / "NoteStore.sqlite-shm"
    wal_path.write_text("wal", encoding="utf-8")
    shm_path.write_text("shm", encoding="utf-8")

    wal.wal_isolate(db_dir, WalAction.COPY_ONLY, "WAL_Isolation", allow_original=False)
    iso_dir = db_dir / "WAL_Isolation"
    assert (iso_dir / wal_path.name).exists()
    assert (iso_dir / shm_path.name).exists()

    wal.wal_isolate(db_dir, WalAction.ISOLATE, "WAL_Isolation", allow_original=False)
    assert not wal_path.exists()
    assert (iso_dir / wal_path.name).exists()

    wal.wal_isolate(db_dir, WalAction.RESTORE, "WAL_Isolation", allow_original=False)
    assert wal_path.exists()


def test_wal_diff_statuses(tmp_path: Path) -> None:
    wal_a = tmp_path / "a.wal"
    wal_b = tmp_path / "b.wal"
    _build_wal(wal_a, 512, [(1, b"A"), (3, b"C")])
    _build_wal(wal_b, 512, [(1, b"B"), (2, b"D")])

    out_dir = tmp_path / "diff"
    summary = wal.wal_diff(wal_a, wal_b, out_dir, max_frames=10, page_size_override=0, run_ts="20260101_000000")
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["added"] == 1
    assert payload["removed"] == 1
    assert payload["changed"] == 1


def test_wal_diff_page_size_mismatch(tmp_path: Path) -> None:
    wal_a = tmp_path / "a.wal"
    wal_b = tmp_path / "b.wal"
    _build_wal(wal_a, 512, [(1, b"A")])
    _build_wal(wal_b, 1024, [(1, b"B")])
    with pytest.raises(RuntimeError):
        wal.wal_diff(wal_a, wal_b, tmp_path / "out", max_frames=5, page_size_override=0, run_ts="20260101_000000")


def test_wal_extract_dump_pages_and_strings(tmp_path: Path) -> None:
    wal_path = tmp_path / "extract.wal"
    _build_wal(wal_path, 512, [(1, b"alpha secret"), (1, b"alpha secret v2")])
    out_dir = tmp_path / "out"
    meta = wal.wal_extract(
        root_dir=tmp_path,
        out_dir=out_dir,
        keyword="secret",
        max_frames=10,
        page_size_override=0,
        dump_pages=True,
        dump_only_duplicates=False,
        strings_on=True,
        strings_min_len=3,
        strings_max_chars=200,
        run_ts="20260101_000000",
        wal_path=wal_path,
    )
    assert meta.exists()
    wal_dir = out_dir / "extract_wal" if (out_dir / "extract_wal").exists() else out_dir
    assert any(p.name.startswith("wal_frames_") for p in wal_dir.rglob("wal_frames_*.csv"))
