import sqlite3
from pathlib import Path

from notes_recovery.services.timeline import build_timeline


def test_build_timeline_minimal(tmp_path: Path) -> None:
    root = tmp_path / "Notes_Forensics"
    db_dir = root / "DB_Backup"
    out_dir = root / "Timeline"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "NoteStore.sqlite"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE ZICCLOUDSYNCINGOBJECT ("
            "Z_PK INTEGER, ZIDENTIFIER TEXT, ZTITLE1 TEXT, ZSNIPPET TEXT, "
            "ZCREATIONDATE REAL, ZMODIFICATIONDATE REAL, ZDELETEDDATE REAL, "
            "ZMARKEDFORDELETION INTEGER, ZLASTOPENEDDATE REAL, ZLASTVIEWEDMODIFICATIONDATE REAL)"
        )
        conn.execute(
            "INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "id-1", "title", "snippet", 100000.0, 100000.0, None, 0, None, None),
        )
        conn.commit()
    finally:
        conn.close()

    outputs = build_timeline(
        root_dir=root,
        out_dir=out_dir,
        keyword="title",
        max_notes=50,
        max_events=200,
        spotlight_max_files=0,
        include_fs=False,
        enable_plotly=False,
        run_ts="20260101_000000",
    )

    assert outputs
    assert any(Path(path).exists() for path in outputs.values() if path)
