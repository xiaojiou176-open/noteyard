from __future__ import annotations

import pathlib

import pytest

from notes_recovery import io


def test_ensure_safe_output_dir_checks(tmp_path: pathlib.Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    out_file = tmp_path / "out.txt"
    out_file.write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError):
        io.ensure_safe_output_dir(out_file, [src], "test")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    with pytest.raises(RuntimeError):
        io.ensure_safe_output_dir(out_dir, [out_dir], "test")

    nested = out_dir / "nested"
    nested.mkdir()
    with pytest.raises(RuntimeError):
        io.ensure_safe_output_dir(nested, [out_dir], "test")

    with pytest.raises(RuntimeError):
        io.ensure_safe_output_dir(out_dir, [nested], "test")


def test_read_text_helpers(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("hello world", encoding="utf-8")
    assert io.safe_read_text(path, 5) == "hello"
    text, truncated = io.read_text_limited(path, 5)
    assert text == "hello"
    assert truncated is True


def test_hash_and_requirements(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "data.bin"
    path.write_bytes(b"abc")
    digest = io.hash_file(path)
    assert len(digest) == 64
    hmac_digest = io.compute_hmac_sha256(path, "key")
    assert len(hmac_digest) == 64

    with pytest.raises(RuntimeError):
        io.require_positive_int(0, "pos")
    with pytest.raises(RuntimeError):
        io.require_non_negative_int(-1, "nonneg")
    with pytest.raises(RuntimeError):
        io.require_float_range(1.1, "range", 0.0, 1.0)
    with pytest.raises(RuntimeError):
        io.require_non_negative_float(-0.1, "float")
