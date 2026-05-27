from __future__ import annotations

import struct
from pathlib import Path

import pytest

from notes_recovery.services import freelist


def _write_header(path: Path, page_size_raw: int, freelist_trunk: int = 0, freelist_count: int = 0) -> None:
    header = bytearray(b"SQLite format 3\x00" + b"\x00" * (freelist.SQLITE_HEADER_SIZE - 16))
    header[16:18] = struct.pack(">H", page_size_raw)
    header[32:36] = struct.pack(">I", freelist_trunk)
    header[36:40] = struct.pack(">I", freelist_count)
    path.write_bytes(bytes(header))


def test_parse_sqlite_header_page_size_65536(tmp_path: Path) -> None:
    db_path = tmp_path / "NoteStore.sqlite"
    _write_header(db_path, page_size_raw=1)
    header = freelist.parse_sqlite_header(db_path)
    assert header["page_size"] == 65536


def test_parse_sqlite_header_invalid_page_size(tmp_path: Path) -> None:
    db_path = tmp_path / "NoteStore.sqlite"
    _write_header(db_path, page_size_raw=100)
    with pytest.raises(RuntimeError):
        freelist.parse_sqlite_header(db_path)


def test_read_page_and_collect_empty(tmp_path: Path) -> None:
    db_path = tmp_path / "NoteStore.sqlite"
    _write_header(db_path, page_size_raw=512)
    assert freelist.read_page(db_path, 0, 512) == b""
    pages = freelist.collect_freelist_pages(db_path, 512, first_trunk=0, max_pages=10)
    assert pages == []


def _write_sqlite_with_ascii_leaf(path: Path) -> None:
    page_size = 512
    header = bytearray(b"SQLite format 3\x00" + b"\x00" * (freelist.SQLITE_HEADER_SIZE - 16))
    header[16:18] = struct.pack(">H", page_size)
    header[32:36] = struct.pack(">I", 2)  # freelist trunk page
    header[36:40] = struct.pack(">I", 2)  # freelist count
    page1 = bytes(header) + b"\x00" * (page_size - len(header))

    trunk = bytearray(b"\x00" * page_size)
    trunk[0:4] = struct.pack(">I", 0)  # next trunk
    trunk[4:8] = struct.pack(">I", 1)  # leaf count
    trunk[8:12] = struct.pack(">I", 3)  # leaf page

    leaf = bytearray(b"\x00" * page_size)
    leaf[0:64] = b"secret_freelist_payload"

    path.write_bytes(page1 + bytes(trunk) + bytes(leaf))


def test_freelist_carve_ascii_fallback_hits(tmp_path: Path) -> None:
    db_path = tmp_path / "NoteStore.sqlite"
    _write_sqlite_with_ascii_leaf(db_path)
    out_dir = tmp_path / "out"
    meta = freelist.freelist_carve(
        db_path=db_path,
        out_dir=out_dir,
        keyword="secret",
        min_text_len=6,
        max_pages=10,
        max_output_mb=1,
        max_chars=200,
        run_ts="20260101_000000",
    )
    assert meta.exists()
    assert any(p.name.startswith("freelist_") for p in out_dir.glob("freelist_*.txt"))
