from __future__ import annotations

from pathlib import Path

import pandas as pd

from notes_recovery.apps import dashboard


def test_dashboard_edge_cases(tmp_path: Path) -> None:
    dashboard.pd = pd
    root = tmp_path / "root"
    root.mkdir()

    assert dashboard.find_latest_file(root, "*.missing", recursive=False) is None
    assert dashboard.find_latest_file(root / "nope", "*.csv", recursive=False) is None

    review_path = tmp_path / "review.csv"
    missing_df = dashboard.load_review_csv(review_path)
    assert missing_df is not None
    assert "stitched_id" in missing_df.columns

    bad_path = tmp_path / "bad_dir"
    bad_path.mkdir()
    bad_df = dashboard.load_review_csv(bad_path)
    assert bad_df is not None

    empty_df = pd.DataFrame(columns=["stitched_id", "verdict"])
    unchanged = dashboard.upsert_review_row(empty_df, {"verdict": "skip"})
    assert unchanged is empty_df

    assert dashboard.extract_source_path("") is None
    assert dashboard.extract_source_path("/no/such/file::x") is None

    manifest = tmp_path / "manifest.csv"
    manifest.write_text("id,source_detail\nnotint,abc\n", encoding="utf-8")
    assert dashboard.build_fragment_lookup(manifest) == {}
