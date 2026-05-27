from __future__ import annotations

import json
from pathlib import Path

from notes_recovery.core import text_bundle


def test_csv_summary_and_markdown_helpers(tmp_path: Path) -> None:
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("col1,col2\nhello,world\nalpha,beta\n", encoding="utf-8")
    summary = text_bundle.csv_summary(csv_path, keyword="hello", max_items=5)
    assert summary["matched"] == 1

    long_cell = "x" * 200
    escaped = text_bundle.markdown_escape_cell(long_cell, max_len=10)
    assert escaped.endswith("...")


def test_generate_text_bundle(tmp_path: Path) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    root_dir.mkdir()
    (root_dir / "Query_Output").mkdir()
    (root_dir / "Recovered_Blobs").mkdir()

    text_file = root_dir / "Query_Output" / "notes.txt"
    text_file.write_text("hello bundle", encoding="utf-8")
    csv_file = root_dir / "Query_Output" / "hits.csv"
    csv_file.write_text("a,b\n1,2\n", encoding="utf-8")

    manifest = root_dir / "Recovered_Blobs" / "manifest.jsonl"
    manifest.write_text(json.dumps({"output": str(text_file), "offset": 0, "text_len": 12}) + "\n", encoding="utf-8")

    bundle_dir = text_bundle.generate_text_bundle(root_dir, run_ts="20260101_000000", keyword="hello")
    assert bundle_dir.exists()
    assert any(p.name.startswith("inventory_") for p in bundle_dir.glob("inventory_*.md"))


def test_bundle_name_helpers_and_markdowns(tmp_path: Path) -> None:
    seen: dict[str, int] = {}
    rel = Path("a/b/c.txt")
    name1 = text_bundle.build_bundle_filename(rel, "20260101", "suffix", ".md", seen)
    name2 = text_bundle.build_bundle_filename(rel, "20260101", "suffix", ".md", seen)
    assert name1 != name2

    src = tmp_path / "note.txt"
    src.write_text("hello", encoding="utf-8")
    md_path = tmp_path / "note.md"
    text_bundle.write_text_markdown(src, md_path, "Title", max_chars=10)
    assert md_path.exists()

    long_src = tmp_path / "long.txt"
    long_src.write_text("x" * 50, encoding="utf-8")
    long_md = tmp_path / "long.md"
    text_bundle.write_text_markdown(long_src, long_md, "Long", max_chars=10)
    assert "truncated" in long_md.read_text(encoding="utf-8")

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")
    csv_md = tmp_path / "data.md"
    text_bundle.write_csv_markdown(csv_path, csv_md, keyword="1", max_rows=5)
    assert csv_md.exists()

    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")
    empty_md = tmp_path / "empty.md"
    text_bundle.write_csv_markdown(empty_csv, empty_md, keyword=None, max_rows=5)
    assert "No header was found" in empty_md.read_text(encoding="utf-8")

    missing_summary = text_bundle.csv_summary(tmp_path / "missing.csv", keyword=None, max_items=5)
    assert missing_summary["header"] == []

    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"output": "x", "offset": 0, "text_len": 1}) + "\n", encoding="utf-8")
    manifest_md = tmp_path / "manifest.md"
    text_bundle.write_manifest_markdown(manifest, manifest_md, max_rows=5)
    assert manifest_md.exists()

    bad_manifest = tmp_path / "bad_manifest.jsonl"
    bad_manifest.write_text("not-json\n", encoding="utf-8")
    bad_md = tmp_path / "bad_manifest.md"
    text_bundle.write_manifest_markdown(bad_manifest, bad_md, max_rows=5)
    assert "No preview rows are available" in bad_md.read_text(encoding="utf-8")
