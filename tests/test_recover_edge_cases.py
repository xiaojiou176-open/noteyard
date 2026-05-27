from __future__ import annotations

from pathlib import Path

import pytest

import notes_recovery.services.recover as recover
from notes_recovery.core.keywords import build_variants_for_keywords


def test_sqlite_recover_options_and_missing(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "db.sqlite"
    db_path.write_text("db", encoding="utf-8")
    out_dir = tmp_path / "out"

    class Dummy:
        def __init__(self, stderr: str = ""):
            self.stderr = stderr

    def fake_run(*_args, **_kwargs):
        return Dummy(stderr="warn")

    monkeypatch.setattr(recover, "get_sqlite3_path", lambda: Path("/usr/bin/sqlite3"))
    monkeypatch.setattr(recover.subprocess, "run", fake_run)

    recovered = recover.sqlite_recover(db_path, out_dir, ignore_freelist=True, lost_and_found="lost")
    assert recovered.name.endswith("_recovered.sqlite")

    with pytest.raises(RuntimeError):
        recover.sqlite_recover(tmp_path / "missing.sqlite", out_dir, False, "")


def test_collect_fragments_edge_cases(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "root"
    blobs = root / "Recovered_Blobs"
    blobs.mkdir(parents=True)
    (blobs / "blob.txt").write_text("hello", encoding="utf-8")

    variants_map = build_variants_for_keywords(["hello"])

    frags = recover.collect_fragments_from_blobs(root, variants_map, match_all=False, max_chars=10, max_items=0)
    assert frags == []

    plugins_dir = root / "Plugins_Output"
    plugins_dir.mkdir()
    (plugins_dir / "subdir").mkdir()
    frags = recover.collect_fragments_from_plugins(root, variants_map, match_all=False, max_chars=10, max_items=1)
    assert frags == []

    query_dir = root / "Query_Output"
    query_dir.mkdir()
    (query_dir / "notes.csv").write_text("col\n\n", encoding="utf-8")

    monkeypatch.setattr(recover, "should_skip_recovery_path", lambda _p: False)
    frags = recover.collect_fragments_from_csv(root, variants_map, match_all=False, max_rows=0)
    assert frags == []

    text_dir = root / "Cache_Backup"
    text_dir.mkdir()
    (text_dir / "note.txt").write_text("hello", encoding="utf-8")
    frags = recover.collect_fragments_from_text_files(root, variants_map, match_all=False, max_chars=10, max_files=0, max_file_mb=1)
    assert frags == []


def test_read_binary_preview_zero(tmp_path: Path) -> None:
    path = tmp_path / "bin.dat"
    path.write_bytes(b"data")
    assert recover.read_binary_preview(path, 0, preview_bytes=0) == ""
