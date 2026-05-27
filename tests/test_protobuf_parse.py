import gzip
import sqlite3
from pathlib import Path

import notes_recovery.services.protobuf as protobuf


def _build_icloud_db(path: Path, payload: bytes) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE ZICCLOUDSYNCINGOBJECT (Z_PK INTEGER, ZIDENTIFIER TEXT, ZTITLE1 TEXT, ZSNIPPET TEXT, ZNOTEDATA INTEGER)"
    )
    conn.execute(
        "CREATE TABLE ZICNOTEDATA (Z_PK INTEGER, ZDATA BLOB)"
    )
    conn.execute(
        "INSERT INTO ZICNOTEDATA VALUES (?, ?)",
        (1, payload),
    )
    conn.execute(
        "INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES (?, ?, ?, ?, ?)",
        (1, "note-id", "Title", "Snippet", 1),
    )
    conn.commit()
    conn.close()


def test_parse_notes_protobuf(monkeypatch, tmp_path: Path) -> None:
    payload = gzip.compress(b"protobuf payload")
    db_path = tmp_path / "notes.sqlite"
    _build_icloud_db(db_path, payload)

    def fake_decode(_payload):
        message = {
            "text": "This is a long note with http://example.com and com.apple.notes.table "
                    "plus uuid 123e4567-e89b-12d3-a456-426614174000",
            "runs": [
                {"a": 1, "b": 2, "c": "font"},
                {"a": 3, "b": 4, "c": "bold"},
                {"a": 5, "b": 6, "c": "italic"},
            ],
            "uti": "public.jpeg",
        }
        return message, {"1": {"type": "string"}}

    monkeypatch.setattr(protobuf, "decode_protobuf_message", fake_decode)

    out_dir = tmp_path / "out"
    manifest = protobuf.parse_notes_protobuf(
        db_path,
        out_dir,
        keyword="Title",
        max_notes=5,
        max_zdata_mb=1,
        run_ts="20260101_000000",
    )

    assert manifest.exists()
    notes_dir = out_dir / "Notes"
    assert any(notes_dir.glob("*.json"))
    assert any(notes_dir.glob("*.md"))
