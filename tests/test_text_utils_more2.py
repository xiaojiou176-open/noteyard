from __future__ import annotations

from pathlib import Path

from notes_recovery.utils import text as text_utils


def test_text_utils_edges(tmp_path: Path) -> None:
    assert text_utils.extract_urls("") == []
    assert text_utils.html_to_text("") == ""
    assert text_utils.strip_html_tags("") == ""

    assert text_utils.infer_title_from_text(Path("note.txt"), "") == "note"
    assert text_utils.normalize_whitespace("a\n b") == "a b"
    assert text_utils.normalize_loose("a b!") == "ab"
