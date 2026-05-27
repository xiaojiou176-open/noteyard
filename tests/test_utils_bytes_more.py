from pathlib import Path

from notes_recovery.utils import bytes as bytes_utils


def test_read_binary_window_and_hex_dump(tmp_path: Path) -> None:
    path = tmp_path / "bin.dat"
    path.write_bytes(b"0123456789abcdef")
    window = bytes_utils.read_binary_window(path, offset=4, window_bytes=6)
    assert window
    dump = bytes_utils.hex_dump(window)
    assert "00000000" in dump


def test_extract_printable_strings_and_utf16(tmp_path: Path) -> None:
    ascii_path = tmp_path / "ascii.bin"
    ascii_path.write_bytes(b"\x00hello\x00world\x00")
    text = bytes_utils.extract_printable_strings(ascii_path, min_len=3, max_chars=200)
    assert "hello" in text

    utf16_path = tmp_path / "utf16.bin"
    utf16_path.write_bytes("hi unicode".encode("utf-16le"))
    utf16_text = bytes_utils.extract_utf16_strings(utf16_path, "utf-16le", 2, 200, 64)
    assert "hi" in utf16_text
