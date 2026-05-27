import struct
from pathlib import Path

from notes_recovery.config import WAL_MAGIC_LE
from notes_recovery.services.wal import parse_wal_header
import pytest


def test_parse_wal_header(tmp_path: Path) -> None:
    path = tmp_path / "test.wal"
    header = struct.pack(">I", WAL_MAGIC_LE)
    # For WAL_MAGIC_LE, parse uses little-endian for the rest.
    header += struct.pack("<7I", 1, 4096, 0, 0, 0, 0, 0)
    path.write_bytes(header + b"\x00" * 8)

    info = parse_wal_header(path, 0)
    assert info["page_size"] == 4096


def test_parse_wal_header_invalid(tmp_path: Path) -> None:
    bad_magic = tmp_path / "bad_magic.wal"
    bad_magic.write_bytes(b"\x00" * 32)
    with pytest.raises(RuntimeError):
        parse_wal_header(bad_magic, 0)

    bad_page = tmp_path / "bad_page.wal"
    header = struct.pack(">I", WAL_MAGIC_LE)
    header += struct.pack("<7I", 1, 123, 0, 0, 0, 0, 0)
    bad_page.write_bytes(header + b"\x00" * 8)
    with pytest.raises(RuntimeError):
        parse_wal_header(bad_page, 0)
