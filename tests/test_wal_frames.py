import struct
from pathlib import Path

from notes_recovery.config import WAL_MAGIC_LE
from notes_recovery.services.wal import count_wal_page_occurrences, iter_wal_frames, parse_wal_header


def _write_min_wal(path: Path, page_size: int = 512) -> None:
    header = struct.pack(">I", WAL_MAGIC_LE)
    header += struct.pack("<7I", 1, page_size, 0, 0, 0, 0, 0)
    frame_header = struct.pack("<6I", 1, 0, 0, 0, 0, 0)
    page = b"\x00" * page_size
    path.write_bytes(header + frame_header + page)


def test_wal_count_and_iter(tmp_path: Path) -> None:
    wal = tmp_path / "NoteStore.sqlite-wal"
    _write_min_wal(wal, page_size=512)

    info = parse_wal_header(wal, 0)
    counts, frames, trailing = count_wal_page_occurrences(
        wal, info["page_size"], "<", max_frames=10
    )
    assert frames == 1
    assert counts.get(1) == 1
    assert trailing == 0

    frames_list = list(iter_wal_frames(wal, info["page_size"], "<", max_frames=10))
    assert len(frames_list) == 1
