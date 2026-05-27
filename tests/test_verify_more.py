from pathlib import Path

from notes_recovery.services.verify import verify_hits


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(header) + "\n")
        for row in rows:
            f.write(",".join(str(item) for item in row) + "\n")


def test_verify_hits_with_plugins(tmp_path: Path) -> None:
    root_dir = tmp_path / "root"
    root_dir.mkdir()

    query_dir = root_dir / "Query_Output"
    blobs_dir = root_dir / "Recovered_Blobs"
    plugins_dir = root_dir / "Plugins_Output"
    db_dir = root_dir / "DB_Backup"

    for directory in (query_dir, blobs_dir, plugins_dir, db_dir):
        directory.mkdir(parents=True)

    _write_csv(query_dir / "query.csv", ["col"], [["Alpha"], ["Beta"]])
    (blobs_dir / "blob_001.txt").write_text("Alpha text", encoding="utf-8")
    (plugins_dir / "plugin.log").write_text("Alpha plugin", encoding="utf-8")
    (db_dir / "NoteStore.sqlite").write_text("Alpha binary", encoding="utf-8")

    out_dir = root_dir / "Verification"
    verify_hits(
        root_dir=root_dir,
        keyword="Alpha",
        top_n=5,
        preview_len=50,
        out_dir=out_dir,
        deep=True,
        deep_max_mb=1,
        deep_max_hits_per_file=10,
        match_all=False,
        fuzzy=False,
        fuzzy_threshold=0.5,
        fuzzy_boost=1.0,
        fuzzy_max_len=200,
        run_ts="20260101_000000",
        deep_all=False,
    )

    outputs = list(out_dir.glob("*.csv"))
    assert outputs
