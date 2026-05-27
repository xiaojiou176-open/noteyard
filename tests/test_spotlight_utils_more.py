from __future__ import annotations

import datetime
from pathlib import Path

from notes_recovery.services import spotlight
from notes_recovery.models import SpotlightIndexType


def test_spotlight_helpers(tmp_path: Path) -> None:
    assert spotlight.safe_sqlite_ident('a"b') == '"a""b"'
    assert spotlight.classify_spotlight_index_type(Path("/tmp/cs_default.db")) == SpotlightIndexType.DEFAULT
    assert spotlight.classify_spotlight_index_type(Path("/tmp/cs_priority.db")) == SpotlightIndexType.PRIORITY
    assert spotlight.classify_spotlight_index_type(Path("/tmp/other.db")) == SpotlightIndexType.OTHER

    assert spotlight.is_spotlight_deep_candidate(Path("/tmp/spotlightknowledgeevents.db"))
    assert spotlight.is_spotlight_deep_candidate(Path("/tmp/indexstate"))
    assert spotlight.is_spotlight_deep_candidate(Path("/tmp/file.plist"))

    ts = spotlight.normalize_spotlight_timestamp(1700000000)
    assert isinstance(ts, datetime.datetime)

    value = spotlight.extract_strings_from_value(b"hello\x00world", max_chars=20)
    assert "hello" in value


def test_is_sqlite_header(tmp_path: Path) -> None:
    db_path = tmp_path / "file.db"
    db_path.write_bytes(b"SQLite format 3\x00")
    assert spotlight.is_sqlite_header(db_path)
    other = tmp_path / "file.bin"
    other.write_bytes(b"not sqlite")
    assert not spotlight.is_sqlite_header(other)
