from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from notes_recovery.apps import dashboard


def _reset_pd(original):
    dashboard.pd = original


def test_dashboard_helper_branches(tmp_path: Path, monkeypatch) -> None:
    original_pd = dashboard.pd
    try:
        dashboard.pd = None
        assert dashboard.load_csv(tmp_path / "missing.csv") is None
        assert dashboard.load_review_csv(tmp_path / "missing.csv") is None
        assert dashboard.save_review_csv(tmp_path / "out.csv", None) is False
        assert dashboard.upsert_review_row(None, {"stitched_id": 1}) is None
    finally:
        _reset_pd(original_pd)

    dashboard.pd = pd
    def boom_read_csv(*_args, **_kwargs):
        raise RuntimeError("read csv fail")

    original_read_csv = pd.read_csv
    monkeypatch.setattr(pd, "read_csv", boom_read_csv)
    assert dashboard.load_csv(tmp_path / "bad.csv") is None

    monkeypatch.setattr(pd, "read_csv", original_read_csv)
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad", encoding="utf-8")
    assert dashboard.load_json(bad_json) is None

    review_path = tmp_path / "review.csv"
    empty_df = dashboard.load_review_csv(review_path)
    assert empty_df is not None
    assert "stitched_id" in empty_df.columns

    df = pd.DataFrame([{"stitched_id": 1, "verdict": "todo"}])
    row = {"stitched_id": 2, "verdict": "new"}
    updated = dashboard.upsert_review_row(df, row)
    assert 2 in updated["stitched_id"].values

    assert dashboard.upsert_review_row(df, {"note": "skip"}) is df

    bad_manifest = tmp_path / "manifest.csv"
    bad_manifest.write_text("id,source_detail\nx,noop\n", encoding="utf-8")
    lookup = dashboard.build_fragment_lookup(bad_manifest)
    assert lookup == {}

    assert dashboard.extract_source_path("") is None
    assert dashboard.extract_source_path(" ::detail") is None
    assert dashboard.extract_source_path("/not/exist::col") is None

    empty_manifest = tmp_path / "empty_manifest.csv"
    empty_manifest.write_text("id,source_detail\n", encoding="utf-8")
    assert dashboard.build_fragment_lookup(empty_manifest) == {}

    df2 = pd.DataFrame([{"stitched_id": "abc", "verdict": "x"}])
    updated = dashboard.upsert_review_row(df2, {"stitched_id": "abc", "verdict": "y"})
    assert updated.loc[updated["stitched_id"] == "abc", "verdict"].iloc[0] == "y"

    root = tmp_path / "root"
    root.mkdir()
    f1 = root / "a.txt"
    f2 = root / "b.txt"
    f1.write_text("a", encoding="utf-8")
    f2.write_text("b", encoding="utf-8")
    time.sleep(0.01)
    f2.touch()
    latest = dashboard.find_latest_file(root, "*.txt", recursive=False)
    assert latest == f2

    def boom(*_args, **_kwargs):
        raise RuntimeError("fail")

    df = pd.DataFrame([{"stitched_id": 1}])
    monkeypatch.setattr(df, "to_csv", boom)
    assert dashboard.save_review_csv(tmp_path / "fail.csv", df) is False

    _reset_pd(original_pd)
