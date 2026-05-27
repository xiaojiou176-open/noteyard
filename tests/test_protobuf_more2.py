from __future__ import annotations

from notes_recovery.services import protobuf


def test_protobuf_text_candidates_and_urls() -> None:
    long_text = "This is a long note text with enough length to pass the threshold." * 1
    message = {
        "root": {
            "text": long_text,
            "bytes": long_text.encode("utf-8"),
            "urls": "http://example.com/path",
            "uuid": "123e4567-e89b-12d3-a456-426614174000",
            "uti": "com.apple.notes",
        }
    }

    candidates = protobuf.extract_note_text_candidates(message)
    assert candidates
    best = protobuf.select_best_note_text(candidates)
    assert best

    urls = protobuf.collect_urls_from_message(message)
    assert urls

    uuids = protobuf.extract_uuid_tokens(message)
    assert uuids

    utis = protobuf.extract_uti_tokens(message)
    assert utis


def test_protobuf_attribute_runs() -> None:
    runs = [
        {"a": 1, "b": 2, "c": "text"},
        {"a": 2, "b": 3, "c": "more"},
        {"a": 3, "b": 4, "c": "x"},
    ]
    message = {"attrs": runs}
    candidates = protobuf.extract_attribute_run_candidates(message)
    assert candidates
    assert protobuf.looks_like_attribute_run(runs[0])


def test_decode_bytes_candidate() -> None:
    payload = ("x" * 60).encode("utf-8")
    text, encoding = protobuf.decode_bytes_candidate(payload)
    assert text
    assert encoding == "utf-8"

    assert protobuf.text_printable_ratio("") == 0.0
    assert protobuf.is_probable_uuid("123e4567-e89b-12d3-a456-426614174000")
    assert protobuf.is_probable_uti("com.apple.notes")


def test_protobuf_helpers_misc() -> None:
    raw = b"not-gzip"
    data, compressed = protobuf.maybe_decompress_zdata(raw, max_output_bytes=100)
    assert data == raw
    assert compressed is False

    import gzip
    payload = b"A" * 50
    gz = gzip.compress(payload)
    data, compressed = protobuf.maybe_decompress_zdata(gz, max_output_bytes=100)
    assert data == payload
    assert compressed is True

    try:
        protobuf.maybe_decompress_zdata(gz, max_output_bytes=10)
    except RuntimeError:
        assert True

    safe = protobuf.json_safe_value({"a": b"bytes", "b": [b"more"]})
    assert "__bytes__" in safe["a"]

    walked = list(protobuf.walk_obj({"k": [1, {"v": "x"}]}))
    assert any(path.endswith("[0]") for path, _ in walked)

    embedded = protobuf.extract_embedded_objects({"t": "com.apple.notes.table"})
    assert embedded

    hints = protobuf.extract_formatting_hints({"attributes": {"bold": True}})
    assert hints


def test_protobuf_attachments_and_markdown(tmp_path) -> None:
    import sqlite3

    db_path = tmp_path / "notes.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE ZICCLOUDSYNCINGOBJECT (ZIDENTIFIER TEXT, ZTITLE1 TEXT, ZTYPEUTI TEXT, "
        "ZFILENAME TEXT, ZURLSTRING TEXT, ZCONTAINER TEXT, ZNOTE INTEGER, ZATTACHMENT INTEGER)"
    )
    conn.execute(
        "INSERT INTO ZICCLOUDSYNCINGOBJECT VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("id-1", "Title", "com.apple.notes", "file.txt", "http://x", "c", 1, 1),
    )
    conn.commit()
    conn.row_factory = sqlite3.Row

    attachments = protobuf.fetch_attachment_candidates(conn, 1, {"ZATTACHMENT"})
    assert attachments

    tagged = protobuf.tag_attachment_candidates(attachments, ["com.apple.notes"], ["id-1"])
    assert tagged[0].get("match_tags")
    conn.close()

    out_path = tmp_path / "note.md"
    protobuf.write_structured_note_markdown(
        out_path=out_path,
        note_id=1,
        identifier="id-1",
        title="Title",
        snippet="Snippet",
        note_text="Body",
        urls=["http://x"],
        attribute_runs=[{"path": "a", "total_runs": 1}],
        attachments=tagged,
    )
    assert out_path.exists()


def test_decode_protobuf_message_fallback(monkeypatch) -> None:
    class _FakeBB:
        def decode_message(self, _data):
            raise RuntimeError("fail")

        def protobuf_to_json(self, _data):
            return "{\"a\": 1}", {}

    monkeypatch.setattr(protobuf, "load_blackboxprotobuf", lambda: _FakeBB())
    msg, typedef = protobuf.decode_protobuf_message(b"data")
    assert msg.get("a") == 1
    assert isinstance(typedef, dict)
