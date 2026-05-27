from pathlib import Path

from notes_recovery.core import time_utils
from notes_recovery.utils import text as text_utils


def test_time_utils() -> None:
    assert time_utils.mac_absolute_to_datetime(None) is None
    dt = time_utils.mac_absolute_to_datetime(0)
    assert dt is not None
    unix = time_utils.unix_to_datetime(0)
    assert unix is not None
    assert time_utils.unix_to_datetime(None) is None
    assert time_utils.mac_absolute_to_datetime("bad") is None


def test_text_utils(tmp_path: Path) -> None:
    assert text_utils.normalize_whitespace("a\n\n b") == "a b"
    assert text_utils.normalize_loose("a-b_c") == "abc"
    assert text_utils.extract_urls("visit http://example.com now")
    assert text_utils.html_to_text("<b>hi</b>") == "hi"
    assert text_utils.strip_html_tags("<b>hi</b>") == "hi"

    md = "# Title\n\nBody"
    path = tmp_path / "note.md"
    assert text_utils.infer_title_from_text(path, md) == "Title"
