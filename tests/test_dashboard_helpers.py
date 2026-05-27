from __future__ import annotations

from pathlib import Path

import pandas as pd

from notes_recovery.apps import dashboard


def test_dashboard_helpers(tmp_path: Path) -> None:
    dashboard.pd = pd
    assert dashboard._try_import("json") is not None
    assert dashboard._try_import("nonexistent_module") is None
    assert dashboard._safe_mtime(tmp_path / "missing.txt") == 0.0
    data_path = tmp_path / "data.json"
    data_path.write_text('{"a": 1}', encoding="utf-8")
    assert dashboard.load_json(data_path) == {"a": 1}

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("id,value\n1,hello\n", encoding="utf-8")
    df = dashboard.load_csv(csv_path)
    assert df is not None
    assert list(df.columns) == ["id", "value"]

    review_path = tmp_path / "review.csv"
    review_df = pd.DataFrame([{"stitched_id": 1, "verdict": "todo"}])
    review_df.to_csv(review_path, index=False)
    loaded = dashboard.load_review_csv(review_path)
    assert loaded is not None

    row = {"stitched_id": 1, "verdict": "done", "note": "ok"}
    updated = dashboard.upsert_review_row(loaded, row)
    assert updated.loc[updated["stitched_id"] == 1, "verdict"].iloc[0] == "done"

    assert dashboard.save_review_csv(review_path, updated)

    src_file = tmp_path / "file.txt"
    src_file.write_text("data", encoding="utf-8")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(f"id,source_detail\n1,{src_file}::t.c\n", encoding="utf-8")
    lookup = dashboard.build_fragment_lookup(manifest)
    assert 1 in lookup

    source = dashboard.extract_source_path(f"{src_file}::table.col")
    assert source and source.name == "file.txt"
