from pathlib import Path

from notes_recovery.services.verify import verify_hits


def test_verify_hits_csv_only(tmp_path: Path) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    query_dir = root_dir / "Query_Output"
    query_dir.mkdir(parents=True)
    csv_path = query_dir / "sample.csv"
    csv_path.write_text("col1,col2\nalpha,beta\n", encoding="utf-8")

    out_dir = root_dir / "Verification"
    run_ts = "20260101_000000"
    verify_hits(
        root_dir=root_dir,
        keyword="alpha",
        top_n=5,
        preview_len=80,
        out_dir=out_dir,
        deep=False,
        fuzzy=False,
        run_ts=run_ts,
    )

    assert (out_dir / f"verify_top5_{run_ts}.txt").exists()
    assert (out_dir / f"verify_hits_{run_ts}.csv").exists()
