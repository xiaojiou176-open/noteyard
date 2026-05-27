from __future__ import annotations

from pathlib import Path

from notes_recovery.core import text_bundle


def test_generate_text_bundle_basic(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    (root / "data.csv").write_text("title,body\nhello,world\n", encoding="utf-8")
    (root / "manifest.jsonl").write_text('{"output":"a","offset":1,"text_len":3}\n', encoding="utf-8")
    (root / "page.html").write_text("<html><body>hi</body></html>", encoding="utf-8")
    (root / "note.txt").write_text("plain text", encoding="utf-8")

    run_ts = "20260101_000000"
    bundle_dir = text_bundle.generate_text_bundle(root, run_ts, keyword="hello")
    assert bundle_dir.exists()

    summary = bundle_dir / f"bundle_summary_{run_ts}.md"
    assert summary.exists()

    outputs = list(bundle_dir.glob("*.md")) + list(bundle_dir.glob("*.txt"))
    assert outputs
