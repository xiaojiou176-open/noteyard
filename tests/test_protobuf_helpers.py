from notes_recovery.services import protobuf


def test_protobuf_helper_scoring() -> None:
    text = "This is a test note with http://example.com"
    score = protobuf.score_text_candidate(text)
    assert score > 0


def test_protobuf_decode_bytes_candidate() -> None:
    data = ("hello world " * 5).encode("utf-8")
    text, encoding = protobuf.decode_bytes_candidate(data)
    assert "hello" in text
    assert encoding in {"utf-8", "utf-16le", "utf-16be"}


def test_json_safe_value_bytes() -> None:
    payload = protobuf.json_safe_value(b"abc")
    assert "__bytes__" in payload
