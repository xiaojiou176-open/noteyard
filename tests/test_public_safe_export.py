from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.check_public_safe_outputs import collect_public_safe_output_errors
from notes_recovery.case_contract import CASE_DIR_RECOVERED_BLOBS_RECOVERED
from notes_recovery.services.public_safe import public_safe_export

SYNTHETIC_PYTHON_EXECUTABLE = "<workspace>/.venv/bin/python"


def test_public_safe_export_redacts_host_metadata(tmp_path: Path) -> None:
    source_root = tmp_path / "case"
    source_root.mkdir()
    (source_root / "DB_Backup").mkdir()
    (source_root / "Recovered_Blobs").mkdir()
    (source_root / "Meta").mkdir()

    run_manifest = source_root / "run_manifest_20260326.json"
    run_manifest.write_text(
        json.dumps(
            {
                "root_dir": str(source_root),
                "runtime": {
                    "python": "3.11.0",
                    "python_executable": SYNTHETIC_PYTHON_EXECUTABLE,
                    "hostname": "demo-host",
                    "cwd": str(source_root),
                },
                "command_line": {
                    "argv": ["notes-recovery", "auto", "--out", str(source_root)],
                    "command": f"notes-recovery auto --out {source_root}",
                },
                "stage_outputs": [str(source_root / "Recovered_Blobs" / "blob_0001.txt")],
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    case_manifest = source_root / "case_manifest_20260326.json"
    case_manifest.write_text(run_manifest.read_text(encoding="utf-8"), encoding="utf-8")

    out_dir = tmp_path / "public"
    outputs = public_safe_export(source_root, out_dir, "20260326_000000")

    assert Path(outputs["public_safe_manifest"]).exists()
    exported_run_manifest = out_dir / "public_safe_run_manifest.json"
    payload = json.loads(exported_run_manifest.read_text(encoding="utf-8"))
    assert payload["root_dir"] == "<case-root>"
    assert "hostname" not in payload["runtime"]
    assert "python_executable" not in payload["runtime"]
    assert "cwd" not in payload["runtime"]
    assert payload["command_line"]["command"] == "<redacted>"
    assert payload["stage_outputs"] == ["<case-root>/Recovered_Blobs/blob_0001.txt"]

    assert collect_public_safe_output_errors([out_dir]) == []


def test_public_safe_export_case_tree_marks_sensitive_dirs(tmp_path: Path) -> None:
    source_root = tmp_path / "case"
    source_root.mkdir()
    (source_root / "DB_Backup").mkdir()
    (source_root / "Text_Bundle_20260326").mkdir()
    (source_root / CASE_DIR_RECOVERED_BLOBS_RECOVERED).mkdir()
    (source_root / "Reports").mkdir()
    (source_root / "Meta").mkdir()

    outputs = public_safe_export(source_root, tmp_path / "public", "20260326_010000")
    case_tree = Path(outputs["public_safe_case_tree"]).read_text(encoding="utf-8")

    assert "DB_Backup/ [omitted]" in case_tree
    assert "Text_Bundle_20260326/ [omitted]" in case_tree
    assert f"{CASE_DIR_RECOVERED_BLOBS_RECOVERED}/ [omitted]" in case_tree
    assert "Reports/ [summarized]" in case_tree
