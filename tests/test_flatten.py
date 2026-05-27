from pathlib import Path

from notes_recovery.services.flatten import flatten_backup


def test_flatten_backup(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "sub").mkdir()
    (src / "sub" / "file.txt").write_text("hello", encoding="utf-8")

    out_dir = tmp_path / "out"
    flatten_backup(src, out_dir, include_manifest=True, run_ts="20260101_000000")
    assert out_dir.exists()
    assert list(out_dir.glob("flatten_manifest_*.csv"))
