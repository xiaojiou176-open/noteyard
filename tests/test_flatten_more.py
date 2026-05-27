from __future__ import annotations

import os
from pathlib import Path

import pytest

from notes_recovery.services.flatten import flatten_backup


def test_flatten_backup_basic_and_manifest(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    (src / "a.txt").write_text("alpha", encoding="utf-8")
    nested = src / "dir"
    nested.mkdir()
    (nested / "b.log").write_text("beta", encoding="utf-8")

    link = src / "link.txt"
    try:
        os.symlink(src / "a.txt", link)
    except OSError:
        link = None

    flatten_backup(src, out, include_manifest=True, run_ts="20260101_000000")

    files = {p.name for p in out.iterdir()}
    assert any(name.startswith("ROOT") for name in files)
    assert any(name.startswith("dir__") for name in files)
    if link is not None:
        assert any("link" in name for name in files)

    manifest = out / "flatten_manifest_20260101_000000.csv"
    assert manifest.exists()
    content = manifest.read_text(encoding="utf-8")
    assert "flat_name" in content


def test_flatten_backup_invalid_dirs(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"
    with pytest.raises(RuntimeError):
        flatten_backup(tmp_path / "missing", out)
    with pytest.raises(RuntimeError):
        flatten_backup(src, src)
    with pytest.raises(RuntimeError):
        flatten_backup(src, src / "sub")
