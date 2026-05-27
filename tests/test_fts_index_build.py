import sqlite3
from pathlib import Path

from notes_recovery.services.fts import build_fts_index


def test_build_fts_index_from_files(tmp_path: Path) -> None:
    root_dir = tmp_path / "root"
    blob_dir = root_dir / "Recovered_Blobs"
    blob_dir.mkdir(parents=True)
    (blob_dir / "blob_0001.txt").write_text("Alpha Beta Gamma", encoding="utf-8")

    out_dir = tmp_path / "out"
    fts_db = build_fts_index(
        root_dir=root_dir,
        out_dir=out_dir,
        keyword="Alpha",
        source_mode="notes",
        db_path=None,
        db_table=None,
        db_columns=[],
        db_title_column=None,
        max_docs=50,
        max_file_mb=1,
        max_text_chars=2000,
    )

    assert fts_db.exists()
    conn = sqlite3.connect(fts_db)
    count = conn.execute("SELECT COUNT(*) FROM docs_meta").fetchone()[0]
    conn.close()
    assert count >= 1
