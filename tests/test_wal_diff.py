from __future__ import annotations

import struct
from pathlib import Path

import pytest

from notes_recovery.config import WAL_MAGIC_LE
from notes_recovery.services import wal


def _write_wal(path: Path, page_size: int, payload: bytes) -> None:
    header = struct.pack(">I", WAL_MAGIC_LE)
    header += struct.pack("<7I", 1, page_size, 0, 0, 0, 0, 0)
    frame_header = struct.pack("<6I", 1, 0, 0, 0, 0, 0)
    path.write_bytes(header + frame_header + payload)


def test_wal_diff_basic(tmp_path: Path) -> None:
    wal_a = tmp_path / "a.wal"
    wal_b = tmp_path / "b.wal"
    _write_wal(wal_a, 512, b"a" * 512)
    _write_wal(wal_b, 512, b"b" * 512)

    out_dir = tmp_path / "out"
    summary = wal.wal_diff(wal_a, wal_b, out_dir, max_frames=10, page_size_override=0, run_ts="20260101_000000")
    assert summary.exists()
    diff_csv = out_dir / "wal_diff_20260101_000000.csv"
    assert diff_csv.exists()


def test_wal_diff_page_size_mismatch(tmp_path: Path) -> None:
    wal_a = tmp_path / "a.wal"
    wal_b = tmp_path / "b.wal"
    _write_wal(wal_a, 512, b"a" * 512)
    _write_wal(wal_b, 1024, b"b" * 1024)
    out_dir = tmp_path / "out"
    with pytest.raises(RuntimeError):
        wal.wal_diff(wal_a, wal_b, out_dir, max_frames=10, page_size_override=0, run_ts="20260101_000000")
