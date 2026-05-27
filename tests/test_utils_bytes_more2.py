from __future__ import annotations

from pathlib import Path

from notes_recovery.utils import bytes as bytes_utils


def test_bytes_edge_cases(tmp_path: Path) -> None:
    assert bytes_utils.is_printable_char("A")
    assert not bytes_utils.is_printable_char("")
    assert not bytes_utils.is_printable_char("\x00")

    missing = tmp_path / "missing.bin"
    assert bytes_utils.read_binary_window(missing, offset=0, window_bytes=10) == b""

    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    assert bytes_utils.read_binary_window(empty, offset=0, window_bytes=10) == b""

    data = tmp_path / "data.bin"
    data.write_bytes(b"0123456789")
    window = bytes_utils.read_binary_window(data, offset=100, window_bytes=4)
    assert window

    assert bytes_utils.hex_dump(b"") == ""

    seqs, carry = bytes_utils.extract_printable_sequences("ab\x00cd", min_len=0, carry="")
    assert "ab" in seqs
    assert carry == "cd"

    assert bytes_utils.merge_text_sections([], max_chars=10) == ""
    assert bytes_utils.merge_text_sections([("A", "text")], max_chars=0) == ""
    merged = bytes_utils.merge_text_sections([("A", "text"), ("B", "more")], max_chars=8)
    assert merged

    data.write_bytes(b"\x00hi\x00")
    assert bytes_utils.extract_printable_strings(data, min_len=1, max_chars=0) == ""

    utf16 = tmp_path / "utf16.bin"
    utf16.write_bytes("hello world".encode("utf-16le"))
    text = bytes_utils.extract_utf16_strings(utf16, "utf-16le", 2, 5, 64)
    assert text
