import json
from pathlib import Path

from notes_recovery.services.report import generate_report


def test_generate_report_basic(tmp_path: Path) -> None:
    root = tmp_path / "Notes_Forensics"
    query_dir = root / "Query_Output"
    blob_dir = root / "Recovered_Blobs"
    query_dir.mkdir(parents=True)
    blob_dir.mkdir(parents=True)
    (query_dir / "sample.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    blob_txt = blob_dir / "blob_0001.txt"
    blob_txt.write_text("hello world", encoding="utf-8")
    manifest = {
        "output": str(blob_txt),
        "offset": 0,
        "text_len": 11,
    }
    (blob_dir / "manifest.jsonl").write_text(json.dumps(manifest), encoding="utf-8")

    out_path = root / "report.html"
    generate_report(root, "hello", out_path, max_items=5)
    assert out_path.exists()
