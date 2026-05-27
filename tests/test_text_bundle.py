from pathlib import Path

from notes_recovery.core.text_bundle import generate_text_bundle


def test_generate_text_bundle(tmp_path: Path) -> None:
    root = tmp_path / "Notes_Forensics"
    root.mkdir()
    csv_dir = root / "Query_Output"
    csv_dir.mkdir()
    (csv_dir / "sample.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (root / "note.txt").write_text("hello", encoding="utf-8")

    bundle_dir = generate_text_bundle(root, "20260101_000000", "hello")
    assert bundle_dir.exists()
    assert list(bundle_dir.glob("inventory_*.md"))
