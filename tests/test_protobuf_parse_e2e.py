from __future__ import annotations

import sqlite3
from pathlib import Path

import notes_recovery.services.protobuf as proto


def test_parse_notes_protobuf_basic(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "notes.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE ZICCLOUDSYNCINGOBJECT (Z_PK INTEGER, ZIDENTIFIER TEXT, ZTITLE1 TEXT, ZSNIPPET TEXT, ZNOTEDATA INTEGER)"
    )
    conn.execute("CREATE TABLE ZICNOTEDATA (Z_PK INTEGER, ZDATA BLOB)")
    conn.execute(
        "INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES (?, ?, ?, ?, ?)",
        (1, "id1", "Title", "Snippet", 1),
    )
    conn.execute("INSERT INTO ZICNOTEDATA VALUES (?, ?)", (1, b"payload"))
    conn.commit()
    conn.close()

    def fake_decode(_payload):
        return {
            "text": "This is a long note body with http://example.com link and com.apple.notes.table.",
            "attributes": [],
        }, {}

    monkeypatch.setattr(proto, "decode_protobuf_message", fake_decode)

    out_dir = tmp_path / "out"
    manifest = proto.parse_notes_protobuf(
        db_path=db_path,
        out_dir=out_dir,
        keyword=None,
        max_notes=5,
        max_zdata_mb=1,
        run_ts="20260101_000000",
    )
    assert manifest.exists()
    assert list(out_dir.rglob("*.json"))
    assert list(out_dir.rglob("*.md"))
