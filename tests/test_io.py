from pathlib import Path

from notes_recovery.io import read_text_limited


def test_read_text_limited_truncates(tmp_path: Path) -> None:
    path = tmp_path / "big.txt"
    path.write_text("a" * 10000, encoding="utf-8")

    text, truncated = read_text_limited(path, 100)

    assert len(text) == 100
    assert truncated is True
