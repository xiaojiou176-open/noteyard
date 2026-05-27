from notes_recovery.core.binary import decode_carved_payload, extract_strings_from_bytes


def test_decode_carved_payload_utf8() -> None:
    data = b"hello-world"
    text, label = decode_carved_payload(data, 200)
    assert "hello-world" in text
    assert label in {"utf-8", "utf-16le", "utf-16be", "ascii_strings", ""}


def test_extract_strings_from_bytes() -> None:
    data = b"\x00abc\x00def\x00"
    text = extract_strings_from_bytes(data, 3, 100)
    assert "abc" in text
