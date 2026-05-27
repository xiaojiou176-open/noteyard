from pathlib import Path

from notes_recovery.services.recover import recover_notes_by_keyword


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(header) + "\n")
        for row in rows:
            f.write(",".join(str(item) for item in row) + "\n")


def test_recover_notes_by_keyword(tmp_path: Path) -> None:
    root_dir = tmp_path / "case"
    out_dir = tmp_path / "recovered"

    recovered_blobs = root_dir / "Recovered_Blobs"
    plugins_output = root_dir / "Plugins_Output"
    query_output = root_dir / "Query_Output"
    cache_backup = root_dir / "Cache_Backup"
    db_backup = root_dir / "DB_Backup"

    for directory in (recovered_blobs, plugins_output, query_output, cache_backup, db_backup):
        directory.mkdir(parents=True)

    # Two overlapping fragments to trigger stitching
    fragment_a = "Alpha Beta Gamma " * 4
    fragment_b = "Gamma Delta Epsilon " * 4
    (recovered_blobs / "blob_0001.txt").write_text(fragment_a, encoding="utf-8")
    (recovered_blobs / "blob_0002.txt").write_text(fragment_b, encoding="utf-8")

    (plugins_output / "plugin.log").write_text("Alpha from plugin log", encoding="utf-8")

    _write_csv(
        query_output / "hits.csv",
        ["col1", "col2"],
        [["Alpha", "row1"], ["Beta", "row2"]],
    )

    (cache_backup / "NotesV7.storedata").write_text("Alpha cache content", encoding="utf-8")

    # Deep scan targets
    (db_backup / "NoteStore.sqlite").write_text("Alpha binary content", encoding="utf-8")

    recover_notes_by_keyword(
        root_dir=root_dir,
        keyword="Alpha",
        out_dir=out_dir,
        min_overlap=5,
        max_fragments=10,
        max_stitch_rounds=50,
        include_deep=True,
        deep_all=True,
        deep_max_mb=1,
        deep_max_hits_per_file=20,
        match_all=False,
        binary_copy=True,
        binary_copy_max_mb=1,
        run_ts="20260101_000000",
    )

    assert (out_dir / "Fragments").exists()
    assert (out_dir / "Stitched").exists()
    summary = out_dir / "Meta" / "recovery_summary_20260101_000000.md"
    assert summary.exists()
