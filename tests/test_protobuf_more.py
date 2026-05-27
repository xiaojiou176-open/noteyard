from __future__ import annotations

import builtins
import gzip
import json
from pathlib import Path

import notes_recovery.services.protobuf as proto
import pytest


def test_protobuf_basic_helpers() -> None:
    data = b"hello world" * 5
    gz = gzip.compress(data)
    out, was_gz = proto.maybe_decompress_zdata(gz, max_output_bytes=1000)
    assert was_gz is True
    assert out.startswith(b"hello")

    payload = proto.json_safe_value(b"hello")
    assert "__bytes__" in payload

    message = {
        "text": "This is a long note body with http://example.com link and com.apple.notes.table.",
        "meta": {"uti": "public.jpeg"},
        "list": ["com.apple.notes"],
        "url": "http://example.com",
    }
    embedded = proto.extract_embedded_objects(message)
    assert embedded

    hints = proto.extract_formatting_hints({"Style": "font"})
    assert hints

    assert proto.is_probable_uuid("123e4567-e89b-12d3-a456-426614174000")
    assert proto.is_probable_uti("public.jpeg")

    candidates = proto.extract_note_text_candidates(message)
    best = proto.select_best_note_text(candidates)
    assert "long note body" in best

    urls = proto.collect_urls_from_message(message)
    assert urls == ["http://example.com"]


def test_decode_protobuf_message_fallback(monkeypatch) -> None:
    class FakeBB:
        def decode_message(self, _data):
            raise RuntimeError("boom")

        def protobuf_to_json(self, _data):
            return json.dumps({"hello": "world"}), {}

    monkeypatch.setattr(proto, "load_blackboxprotobuf", lambda: FakeBB())
    obj, typedef = proto.decode_protobuf_message(b"data")
    assert obj.get("hello") == "world"
    assert isinstance(typedef, dict)


def test_write_structured_note_markdown_branches(tmp_path: Path) -> None:
    out_path = tmp_path / "note.md"
    proto.write_structured_note_markdown(
        out_path,
        note_id=1,
        identifier="",
        title="",
        snippet="",
        note_text="",
        urls=[],
        attribute_runs=[],
        attachments=[],
    )
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "No clear note body text was recovered" in content

    out_path2 = tmp_path / "note2.md"
    proto.write_structured_note_markdown(
        out_path2,
        note_id=2,
        identifier="id",
        title="title",
        snippet="snippet",
        note_text="hello",
        urls=["http://example.com"],
        attribute_runs=[{"path": "p", "total_runs": 2}],
        attachments=[
            {
                "ZIDENTIFIER": "a",
                "ZTYPEUTI": "public.jpeg",
                "ZURLSTRING": "u",
                "ZTITLE1": "t",
                "ZFILENAME": "f",
                "match_tags": ["uti"],
            }
        ],
    )
    assert out_path2.exists()


def test_load_blackboxprotobuf_error(monkeypatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "blackboxprotobuf":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError):
        proto.load_blackboxprotobuf()


def test_maybe_decompress_zdata_error() -> None:
    bad = proto.GZIP_MAGIC + b"not-a-gzip"
    with pytest.raises(RuntimeError):
        proto.maybe_decompress_zdata(bad, max_output_bytes=10)
