from __future__ import annotations

from notes_recovery.core import binary


def test_extract_strings_respects_max_chars() -> None:
    data = b"abc\x00def\x00ghi"
    out = binary.extract_strings_from_bytes(data, min_len=3, max_chars=5)
    assert out.startswith("abc")
    assert len(out) <= 5


def test_decode_carved_payload_ascii_fallback(monkeypatch) -> None:
    monkeypatch.setattr(binary, "choose_best_text_preview_with_label", lambda _c: ("", ""))
    text, label = binary.decode_carved_payload(b"abcd\x00efgh", max_chars=32)
    assert "abcd" in text
    assert label == "ascii_strings"
