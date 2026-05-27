from __future__ import annotations

import types
from pathlib import Path

import pytest

from notes_recovery.services import carve


class _Var:
    def __init__(self, text: str) -> None:
        self.text = text


def test_is_zlib_header_flag_fdic() -> None:
    assert carve.is_zlib_header_bytes(b"\x78\x20") is False


def test_load_lz4_and_lzfse_modules(monkeypatch) -> None:
    fake_frame = types.ModuleType("lz4.frame")
    fake_frame.decompress = lambda data: data[::-1]  # type: ignore[assignment]
    fake_lz4 = types.ModuleType("lz4")
    fake_lz4.frame = fake_frame  # type: ignore[attr-defined]

    monkeypatch.setitem(__import__("sys").modules, "lz4", fake_lz4)
    monkeypatch.setitem(__import__("sys").modules, "lz4.frame", fake_frame)

    assert carve.load_lz4_module() is fake_frame

    def fake_import(name: str):
        if name == "liblzfse":
            mod = types.SimpleNamespace(decompress=lambda data: data)
            return mod
        raise ImportError("nope")

    monkeypatch.setattr(carve.importlib, "import_module", fake_import)
    assert carve.load_lzfse_module() is not None

    def always_fail(_name: str):
        raise ImportError("missing")

    monkeypatch.setattr(carve.importlib, "import_module", always_fail)
    assert carve.load_lzfse_module() is None


def test_try_decompress_window_lz4_lzfse(monkeypatch) -> None:
    monkeypatch.setattr(carve, "load_lz4_module", lambda: types.SimpleNamespace(decompress=lambda data: b"lz4"))
    monkeypatch.setattr(carve, "load_lzfse_module", lambda: types.SimpleNamespace(decompress=lambda data: b"lzfse"))
    assert carve.try_decompress_window(b"x", "lz4") == b"lz4"
    assert carve.try_decompress_window(b"x", "lzfse") == b"lzfse"


def test_try_decompress_at_empty_and_exception(tmp_path: Path, monkeypatch) -> None:
    file_path = tmp_path / "empty.bin"
    file_path.write_bytes(b"")
    data, algo = carve.try_decompress_at(
        file_path,
        offset=0,
        window_size=8,
        algorithms=["gzip"],
        max_window_size=8,
        max_output_bytes=100,
        warned_missing=set(),
    )
    assert data is None
    assert algo == ""

    non_empty = tmp_path / "data.bin"
    non_empty.write_bytes(b"0123456789")

    def boom(_data: bytes, _algo: str):
        raise RuntimeError("decompress fail")

    monkeypatch.setattr(carve, "try_decompress_window", boom)
    data, algo = carve.try_decompress_at(
        non_empty,
        offset=0,
        window_size=8,
        algorithms=["gzip"],
        max_window_size=8,
        max_output_bytes=100,
        warned_missing=set(),
    )
    assert data is None
    assert algo == ""


def test_try_decompress_window_lzfse_none() -> None:
    assert carve.try_decompress_window(b"x", "lzfse") is None
    assert carve.try_decompress_window(b"x", "unknown") is None


def test_text_ratio_and_gzip_header_edges() -> None:
    assert carve.text_printable_ratio("") == 0.0
    assert carve.is_gzip_header_bytes(b"") is False
    assert carve.is_gzip_header_bytes(b"\x00\x00\x00\x00") is False


def test_match_keywords_variant_skip_and_limit(monkeypatch) -> None:
    monkeypatch.setattr(
        carve,
        "build_variants_for_keywords",
        lambda _kw: {"k": [_Var(""), _Var("alpha"), _Var("beta")]},
    )
    assert carve.match_keywords_with_variants("nope", ["k"], max_variants_per_keyword=1) is False


def test_find_gzip_offsets_error(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        list(carve.find_gzip_offsets(tmp_path, chunk_size=8))


def test_carve_gzip_branch_controls(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "db.sqlite"
    db_path.write_text("db", encoding="utf-8")
    out_dir = tmp_path / "out1"
    monkeypatch.setattr(carve, "find_compressed_offsets", lambda *_args, **_kwargs: [(0, "zlib"), (1, "zlib")])
    monkeypatch.setattr(carve, "try_decompress_at", lambda *_args, **_kwargs: (b"data", "zlib"))
    monkeypatch.setattr(carve, "decode_carved_payload", lambda *_args, **_kwargs: ("hello world", "utf-8"))
    carve.carve_gzip(
        db_path,
        out_dir,
        keyword=None,
        max_hits=1,
        window_size=16,
        min_text_len=5,
        min_text_ratio=0.2,
        algorithms=["zlib", "zlib-raw"],
    )
    assert len(list(out_dir.glob("blob_*.txt"))) == 1

    out_dir2 = tmp_path / "out2"
    monkeypatch.setattr(carve, "find_compressed_offsets", lambda *_args, **_kwargs: [(0, "zlib")])
    monkeypatch.setattr(carve, "try_decompress_at", lambda *_args, **_kwargs: (None, ""))
    carve.carve_gzip(
        db_path,
        out_dir2,
        keyword=None,
        max_hits=1,
        window_size=16,
        min_text_len=5,
        min_text_ratio=0.2,
        algorithms=["zlib", "zlib-raw"],
    )
    assert not list(out_dir2.glob("blob_*.txt"))

    out_dir3 = tmp_path / "out3"
    monkeypatch.setattr(carve, "try_decompress_at", lambda *_args, **_kwargs: (b"data", "zlib"))
    monkeypatch.setattr(carve, "decode_carved_payload", lambda *_args, **_kwargs: ("", ""))
    carve.carve_gzip(
        db_path,
        out_dir3,
        keyword=None,
        max_hits=1,
        window_size=16,
        min_text_len=5,
        min_text_ratio=0.2,
        algorithms=["zlib", "zlib-raw"],
    )

    out_dir4 = tmp_path / "out4"
    monkeypatch.setattr(carve, "decode_carved_payload", lambda *_args, **_kwargs: ("x", "utf-8"))
    carve.carve_gzip(
        db_path,
        out_dir4,
        keyword=None,
        max_hits=1,
        window_size=16,
        min_text_len=5,
        min_text_ratio=0.2,
        algorithms=["zlib"],
    )


def test_carve_gzip_write_and_manifest_errors(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "db.sqlite"
    db_path.write_text("db", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(carve, "find_compressed_offsets", lambda *_args, **_kwargs: [(0, "gzip")])
    monkeypatch.setattr(carve, "try_decompress_at", lambda *_args, **_kwargs: (b"data", "gzip"))
    monkeypatch.setattr(carve, "decode_carved_payload", lambda *_args, **_kwargs: ("hello world", "utf-8"))

    out_file = out_dir / "blob_0001_gzip.txt"
    manifest_path = out_dir / "manifest.jsonl"
    original_open = Path.open

    def fake_open(self: Path, *args, **kwargs):
        if self == out_file:
            raise OSError("write fail")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open)
    carve.carve_gzip(
        db_path,
        out_dir,
        keyword=None,
        max_hits=1,
        window_size=16,
        min_text_len=5,
        min_text_ratio=0.2,
    )

    def fake_open_manifest(self: Path, *args, **kwargs):
        if self == manifest_path:
            raise OSError("manifest fail")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open_manifest)
    carve.carve_gzip(
        db_path,
        out_dir,
        keyword=None,
        max_hits=1,
        window_size=16,
        min_text_len=5,
        min_text_ratio=0.2,
    )
