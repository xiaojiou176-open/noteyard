from pathlib import Path

from notes_recovery.cli.main import main


def test_cli_query_e2e(tmp_path: Path, data_dir: Path) -> None:
    base_out = tmp_path / "Query_Output"
    db_path = data_dir / "icloud_min.sqlite"

    code = main(["query", "--db", str(db_path), "--out", str(base_out)])
    assert code == 0

    candidates = list(base_out.parent.glob(f"{base_out.name}_*"))
    assert candidates
    out_dir = candidates[0]
    assert list(out_dir.glob("*.csv"))
