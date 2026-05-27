from __future__ import annotations

from pathlib import Path

from notes_recovery.utils import bytes as bytes_utils


def test_hex_dump_and_read_window(tmp_path: Path) -> None:
    path = tmp_path / "data.bin"
    path.write_bytes(b"\x00\x01\x02abcd")
    dump = bytes_utils.hex_dump(b"\x00\x01\x02")
    assert "00000000" in dump

    window = bytes_utils.read_binary_window(path, offset=2, window_bytes=4)
    assert window

    missing = bytes_utils.read_binary_window(tmp_path / "missing.bin", offset=0, window_bytes=4)
    assert missing == b""
    assert bytes_utils.is_printable_char("\x00") is False
    assert bytes_utils.is_printable_char("A") is True


def test_extract_sequences_and_merge_sections() -> None:
    seqs, carry = bytes_utils.extract_printable_sequences("ab\x00cd", min_len=2, carry="")
    assert seqs == ["ab"]
    assert carry == "cd"

    merged = bytes_utils.merge_text_sections([("A", "hello"), ("B", "world")], max_chars=10)
    assert merged


def test_extract_printable_strings_with_utf16(tmp_path: Path) -> None:
    path = tmp_path / "strings.bin"
    payload = b"ASCII_TEXT\x00" + "utf16".encode("utf-16le")
    path.write_bytes(payload)
    text = bytes_utils.extract_printable_strings(path, min_len=3, max_chars=200)
    assert "ASCII_TEXT" in text

    utf16_text = bytes_utils.extract_utf16_strings(path, "utf-16le", min_len=3, max_chars=200, chunk_size=4)
    assert "utf16" in utf16_text
