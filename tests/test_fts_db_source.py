import sqlite3
from pathlib import Path

from notes_recovery.services.fts import build_fts_index


def test_build_fts_index_from_db(tmp_path: Path) -> None:
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    db_path = root_dir / "notes.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE notes (title TEXT, body TEXT)")
    conn.execute("INSERT INTO notes VALUES (?, ?)", ("Hello", "Alpha body"))
    conn.commit()
    conn.close()

    out_dir = tmp_path / "out"
    fts_db = build_fts_index(
        root_dir=root_dir,
        out_dir=out_dir,
        keyword=None,
        source_mode="db",
        db_path=db_path,
        db_table="notes",
        db_columns=["body"],
        db_title_column="title",
        max_docs=10,
        max_file_mb=1,
        max_text_chars=1000,
    )

    assert fts_db.exists()
    conn = sqlite3.connect(fts_db)
    count = conn.execute("SELECT COUNT(*) FROM docs_meta").fetchone()[0]
    conn.close()
    assert count >= 1
