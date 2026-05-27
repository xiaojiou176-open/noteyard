from __future__ import annotations

from notes_recovery.core import binary


def test_binary_extract_and_decode() -> None:
    assert binary.extract_strings_from_bytes(b"", min_len=2, max_chars=10) == ""
    data = b"ab\x00cdEF\x00ghij"
    extracted = binary.extract_strings_from_bytes(data, min_len=2, max_chars=100)
    assert "ab" in extracted

    empty_text, empty_label = binary.decode_carved_payload(b"", max_chars=10)
    assert empty_text == ""
    assert empty_label == ""

    text, label = binary.decode_carved_payload(b"hello world", max_chars=100)
    assert text
    assert label
