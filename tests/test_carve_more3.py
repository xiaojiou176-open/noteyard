from __future__ import annotations

import zlib
from pathlib import Path

import pytest

from notes_recovery.services import carve


def test_normalize_carve_algorithms_all_and_unknown() -> None:
    algos = carve.normalize_carve_algorithms("all")
    assert "gzip" in algos
    assert "zlib" in algos

    with pytest.raises(RuntimeError):
        carve.normalize_carve_algorithms("nope")

    default_algos = carve.normalize_carve_algorithms(",")
    assert default_algos


def test_header_checks_and_find_offsets(tmp_path: Path) -> None:
    payload = zlib.compress(b"hello world")
    assert carve.is_zlib_header_bytes(payload[:2])
    assert not carve.is_zlib_header_bytes(b"")
    assert not carve.is_zlib_header_bytes(b"\x00\x00")

    assert carve.is_gzip_header_bytes(b"\x1f\x8b\x08\x00")
    assert not carve.is_gzip_header_bytes(b"\x1f\x8b\x07\x00")
    assert not carve.is_gzip_header_bytes(b"\x1f\x8b\x08\xff")

    file_path = tmp_path / "blob.bin"
    file_path.write_bytes(b"xx" + payload + b"yy")

    offsets = list(carve.find_compressed_offsets(file_path, chunk_size=8, algorithms=["zlib"]))
    assert any(offset == 2 and algo == "zlib" for offset, algo in offsets)


def test_try_decompress_at_warns_missing(tmp_path: Path, monkeypatch) -> None:
    payload = zlib.compress(b"secret data")
    file_path = tmp_path / "blob.bin"
    file_path.write_bytes(b"xxxx" + payload + b"zz")

    warned: list[str] = []
    monkeypatch.setattr(carve, "log_warn", lambda msg: warned.append(msg))
    monkeypatch.setattr(carve, "load_lz4_module", lambda: None)

    warned_missing: set[str] = set()
    data, algo = carve.try_decompress_at(
        file_path,
        offset=4,
        window_size=len(payload),
        algorithms=["lz4", "zlib"],
        max_window_size=len(payload),
        max_output_bytes=1024,
        warned_missing=warned_missing,
    )
    assert data == b"secret data"
    assert algo == "zlib"
    assert "lz4" in warned_missing
    assert warned


def test_should_accept_carved_text_ratio() -> None:
    assert not carve.should_accept_carved_text("\x00\x01\x02", min_text_len=2, min_ratio=0.9)
    assert carve.should_accept_carved_text("hello world", min_text_len=5, min_ratio=0.2)


def test_match_keywords_and_zlib_raw() -> None:
    assert carve.match_keywords_with_variants("hello", []) is True
    assert carve.match_keywords_with_variants("secret value", ["secret"]) is True
    assert carve.match_keywords_with_variants("no match", ["secret"]) is False

    comp = zlib.compressobj(wbits=-15)
    raw = comp.compress(b"payload") + comp.flush()
    decoded = carve.try_decompress_window(raw, "zlib-raw")
    assert decoded == b"payload"
