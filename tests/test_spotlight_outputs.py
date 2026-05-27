from __future__ import annotations

from collections import Counter
from pathlib import Path

from notes_recovery.models import SpotlightTokenType
from notes_recovery.services import spotlight


def test_spotlight_output_writers(tmp_path: Path) -> None:
    counters = {
        SpotlightTokenType.QUERY: Counter({"q": 2}),
        SpotlightTokenType.BUNDLE_ID: Counter({"com.apple.notes": 1}),
        SpotlightTokenType.FILE_PATH: Counter({"/tmp/a": 1}),
        SpotlightTokenType.URL: Counter({"http://example.com": 1}),
        SpotlightTokenType.NOTE_ID: Counter({"uuid": 1}),
    }
    tokens_csv = tmp_path / "tokens.csv"
    spotlight.write_spotlight_tokens_csv(tokens_csv, counters, max_items=5)
    assert tokens_csv.exists()

    access_csv = tmp_path / "access.csv"
    spotlight.write_spotlight_access_csv(access_csv, counters, max_items=5)
    assert access_csv.exists()

    events_csv = tmp_path / "events.csv"
    spotlight.write_spotlight_events_csv(events_csv, [("2024-01-01T00:00:00Z", "t", "c", "note", "/tmp/db", "raw")])
    assert events_csv.exists()

    diagnostics_csv = tmp_path / "diag.csv"
    spotlight.write_spotlight_diagnostics_csv(diagnostics_csv, [("/tmp/a", "default", "plist", "1", "ok", "")])
    assert diagnostics_csv.exists()


def test_collect_spotlight_candidates(tmp_path: Path) -> None:
    root = tmp_path / "Spotlight_Backup"
    root.mkdir()
    file1 = root / "cs_default.db"
    file1.write_text("x", encoding="utf-8")
    file2 = root / "cs_priority.db"
    file2.write_text("y", encoding="utf-8")
    candidates = spotlight.collect_spotlight_candidates(root, max_files=1, max_bytes=10)
    assert len(candidates) == 1
