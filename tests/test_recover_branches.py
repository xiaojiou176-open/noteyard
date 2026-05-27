from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from notes_recovery.services import recover
from notes_recovery.core.keywords import build_variants_for_keywords


def _create_sqlite_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()


def test_sqlite_recover_subprocess_failures(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "db.sqlite"
    _create_sqlite_db(db_path)

    def fail_first(*_args, **_kwargs):
        raise recover.subprocess.CalledProcessError(1, ["sqlite3"], "boom")

    monkeypatch.setattr(recover.subprocess, "run", fail_first)
    with pytest.raises(RuntimeError):
        recover.sqlite_recover(db_path, tmp_path / "out", ignore_freelist=False, lost_and_found="")

    calls = {"count": 0}

    def fail_second(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            class _Ok:
                stderr = ""
            return _Ok()
        raise recover.subprocess.CalledProcessError(1, ["sqlite3"], "boom")

    monkeypatch.setattr(recover.subprocess, "run", fail_second)
    with pytest.raises(RuntimeError):
        recover.sqlite_recover(db_path, tmp_path / "out2", ignore_freelist=False, lost_and_found="")


def test_collect_fragments_from_csv_and_text_files(tmp_path: Path) -> None:
    root = tmp_path / "Notes_Forensics"
    query_dir = root / "Query_Output"
    query_dir.mkdir(parents=True)
    csv_path = query_dir / "hits.csv"
    csv_path.write_text("col\n\nsecret\n", encoding="utf-8")

    variants_map = build_variants_for_keywords(["secret"])
    fragments = recover.collect_fragments_from_csv(root, variants_map, match_all=False, max_rows=10)
    assert fragments

    db_dir = root / "DB_Backup"
    db_dir.mkdir()
    bad_file = db_dir / "skip.bin"
    bad_file.write_bytes(b"secret")
    text_fragments = recover.collect_fragments_from_text_files(
        root,
        variants_map,
        match_all=False,
        max_chars=100,
        max_files=10,
        max_file_mb=0,
    )
    assert text_fragments == []
