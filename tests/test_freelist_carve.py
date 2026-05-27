from __future__ import annotations

import struct
from pathlib import Path

import pytest

from notes_recovery.services import freelist


def _write_sqlite_with_freelist(path: Path) -> None:
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


def test_parse_sqlite_header_errors(tmp_path: Path) -> None:
    bad = tmp_path / "bad.sqlite"
    bad.write_bytes(b"short")
    with pytest.raises(RuntimeError):
        freelist.parse_sqlite_header(bad)


def test_freelist_carve_basic(tmp_path: Path) -> None:
    db_path = tmp_path / "NoteStore.sqlite"
    _write_sqlite_with_freelist(db_path)
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


def test_collect_freelist_pages_limits(tmp_path: Path) -> None:
    db_path = tmp_path / "NoteStore.sqlite"
    _write_sqlite_with_freelist(db_path)
    header = freelist.parse_sqlite_header(db_path)
    pages = freelist.collect_freelist_pages(
        db_path=db_path,
        page_size=header["page_size"],
        first_trunk=header["freelist_trunk"],
        max_pages=1,
    )
    assert len(pages) == 1
