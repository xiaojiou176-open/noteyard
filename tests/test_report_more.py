from __future__ import annotations

import json
from pathlib import Path

from notes_recovery.services import report


def test_generate_report_with_plugins_and_carve(tmp_path: Path) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    query_dir = root_dir / "Query_Output"
    blob_dir = root_dir / "Recovered_Blobs"
    plugin_dir = root_dir / "Plugins_Output" / "tool"
    query_dir.mkdir(parents=True)
    blob_dir.mkdir(parents=True)
    plugin_dir.mkdir(parents=True)

    query_csv = query_dir / "notes.csv"
    query_csv.write_text("a,b\nsecret,1\nother,2\n", encoding="utf-8")

    blob_text = blob_dir / "blob.txt"
    blob_text.write_text("secret blob", encoding="utf-8")
    manifest = blob_dir / "manifest.jsonl"
    manifest.write_text(json.dumps({"output": str(blob_text)}) + "\n", encoding="utf-8")

    plugin_log = plugin_dir / "plugin.log"
    plugin_log.write_text("secret plugin", encoding="utf-8")

    out_path = root_dir / "report.html"
    report.generate_report(root_dir, keyword="secret", out_path=out_path, max_items=10)
    assert out_path.exists()
    html = out_path.read_text(encoding="utf-8")
    assert "<mark>secret</mark>" in html


def test_scan_plugin_outputs_empty(tmp_path: Path) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    root_dir.mkdir()
    summary = report.scan_plugin_outputs(root_dir, keyword="secret", max_items=5)
    assert summary["total_files"] == 0
