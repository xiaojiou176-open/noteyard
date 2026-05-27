from __future__ import annotations

import struct
from pathlib import Path

from notes_recovery.config import WAL_MAGIC_LE
from notes_recovery.services import wal


def _write_wal(path: Path, page_size: int, pages: list[int], trailing: bytes = b"") -> None:
    header = struct.pack(">I", WAL_MAGIC_LE)
    header += struct.pack("<7I", 1, page_size, 0, 0, 0, 0, 0)
    frames = []
    for page_no in pages:
        frame_header = struct.pack("<6I", page_no, 0, 0, 0, 0, 0)
        frame_data = b"x" * page_size
        frames.append(frame_header + frame_data)
    path.write_bytes(header + b"".join(frames) + trailing)


def test_count_and_iter_wal_frames(tmp_path: Path) -> None:
    wal_path = tmp_path / "test.wal"
    _write_wal(wal_path, page_size=512, pages=[1, 2], trailing=b"trail")

    counts, frame_count, trailing = wal.count_wal_page_occurrences(
        wal_path,
        page_size=512,
        endian="<",
        max_frames=10,
    )
    assert counts[1] == 1
    assert counts[2] == 1
    assert frame_count == 2
    assert trailing == len(b"trail")

    frames = list(wal.iter_wal_frames(wal_path, page_size=512, endian="<", max_frames=1))
    assert len(frames) == 1
    assert frames[0]["page_no"] == 1
