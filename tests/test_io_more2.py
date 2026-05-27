from __future__ import annotations

from pathlib import Path

import pytest

from notes_recovery import io as io_utils


def test_io_validations_and_reads(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        io_utils.require_positive_int(0, "x")
    with pytest.raises(RuntimeError):
        io_utils.require_non_negative_int(-1, "x")
    with pytest.raises(RuntimeError):
        io_utils.require_float_range(2.0, "x", 0.0, 1.0)
    with pytest.raises(RuntimeError):
        io_utils.require_non_negative_float(-0.1, "x")

    path = tmp_path / "file.txt"
    path.write_text("hello", encoding="utf-8")
    assert io_utils.safe_read_text(path, max_chars=0) == "hello"

    text, truncated = io_utils.read_text_limited(path, max_chars=3)
    assert truncated is True
    assert text == "hel"

    src = tmp_path / "src"
    src.mkdir()
    out_dir = src / "out"
    with pytest.raises(RuntimeError):
        io_utils.ensure_safe_output_dir(out_dir, [src], label="test")
