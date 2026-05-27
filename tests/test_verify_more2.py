from __future__ import annotations

from pathlib import Path

from notes_recovery.services import verify


def test_verify_helpers() -> None:
    assert verify.is_plugin_text_candidate(Path("plugin.log"))
    assert verify.is_plugin_text_candidate(Path("file.TXT"))

    score, coverage = verify.score_verify_hit(
        occurrences=1.0,
        length=0,
        source_weight=1.0,
        keyword_hits=1,
        total_keywords=2,
        fuzzy_ratio=0.5,
        fuzzy_boost=2.0,
    )
    assert score > 0
    assert coverage > 0


def test_verify_hits_match_all_fuzzy(tmp_path: Path) -> None:
    root_dir = tmp_path / "root"
    root_dir.mkdir()

    query_dir = root_dir / "Query_Output"
    blobs_dir = root_dir / "Recovered_Blobs"
    plugins_dir = root_dir / "Plugins_Output"
    db_dir = root_dir / "DB_Backup"

    for directory in (query_dir, blobs_dir, plugins_dir, db_dir):
        directory.mkdir(parents=True)

    (query_dir / "query.csv").write_text("col\nalpha beta\nalpha\n", encoding="utf-8")
    (blobs_dir / "blob_001.txt").write_text("alpha beta text", encoding="utf-8")
    (plugins_dir / "plugin.log").write_text("alpha beta plugin", encoding="utf-8")
    (db_dir / "NoteStore.sqlite").write_text("alpha beta binary", encoding="utf-8")

    out_dir = root_dir / "Verification"
    verify.verify_hits(
        root_dir=root_dir,
        keyword="alpha,beta",
        top_n=5,
        preview_len=50,
        out_dir=out_dir,
        deep=True,
        deep_max_mb=1,
        deep_max_hits_per_file=10,
        match_all=True,
        fuzzy=True,
        fuzzy_threshold=0.5,
        fuzzy_boost=1.0,
        fuzzy_max_len=200,
        run_ts="20260101_000000",
        deep_all=True,
    )

    outputs = list(out_dir.glob("*.csv"))
    assert outputs
