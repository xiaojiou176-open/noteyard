from __future__ import annotations

from pathlib import Path

import pytest

from notes_recovery.services import carve


def test_find_compressed_offsets_invalid_path(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        list(carve.find_compressed_offsets(tmp_path, chunk_size=8, algorithms=["gzip"]))


def test_try_decompress_at_max_output_bytes(tmp_path: Path, monkeypatch) -> None:
    file_path = tmp_path / "blob.bin"
    file_path.write_bytes(b"0123456789")

    def fake_decompress(_data: bytes, _algo: str):
        return b"x" * 100

    monkeypatch.setattr(carve, "try_decompress_window", fake_decompress)
    data, algo = carve.try_decompress_at(
        file_path,
        offset=0,
        window_size=8,
        algorithms=["gzip"],
        max_window_size=8,
        max_output_bytes=10,
        warned_missing=set(),
    )
    assert data is None
    assert algo == ""


def test_carve_gzip_deduplicates_hits(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "db.sqlite"
    db_path.write_text("db", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(carve, "find_compressed_offsets", lambda *_args, **_kwargs: [(0, "gzip"), (1, "gzip")])
    monkeypatch.setattr(carve, "try_decompress_at", lambda *_args, **_kwargs: (b"data", "gzip"))
    monkeypatch.setattr(carve, "decode_carved_payload", lambda *_args, **_kwargs: ("hello world", "utf-8"))

    carve.carve_gzip(
        db_path,
        out_dir,
        keyword=None,
        max_hits=5,
        window_size=16,
        min_text_len=5,
        min_text_ratio=0.2,
    )

    blobs = sorted(out_dir.glob("blob_*.txt"))
    assert len(blobs) == 1


def test_carve_gzip_keyword_miss_and_zero_hits(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "db.sqlite"
    db_path.write_text("db", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(carve, "find_compressed_offsets", lambda *_args, **_kwargs: [(0, "gzip")])
    monkeypatch.setattr(carve, "try_decompress_at", lambda *_args, **_kwargs: (b"data", "gzip"))
    monkeypatch.setattr(carve, "decode_carved_payload", lambda *_args, **_kwargs: ("no match here", "utf-8"))

    carve.carve_gzip(
        db_path,
        out_dir,
        keyword="needle",
        max_hits=3,
        window_size=16,
        min_text_len=5,
        min_text_ratio=0.2,
    )
    assert not list(out_dir.glob("blob_*.txt"))

    monkeypatch.setattr(carve, "decode_carved_payload", lambda *_args, **_kwargs: ("alpha beta", "utf-8"))
    monkeypatch.setattr(carve, "match_keywords_with_variants", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(carve, "evaluate_text_hits", lambda *_args, **_kwargs: (0, 0, 0.0))

    carve.carve_gzip(
        db_path,
        out_dir,
        keyword="alpha",
        max_hits=3,
        window_size=16,
        min_text_len=5,
        min_text_ratio=0.2,
    )
    assert not list(out_dir.glob("blob_*.txt"))
