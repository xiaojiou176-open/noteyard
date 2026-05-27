from __future__ import annotations

import json
from pathlib import Path

from notes_recovery.apps import dashboard


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_case_root(tmp_path: Path, name: str, *, with_ai: bool = True) -> Path:
    root = tmp_path / name
    root.mkdir()
    _write(root / "review_index.md", "# Review Index\n\n- Start with verification.\n")
    _write(root / "run_manifest_20260331_000000.json", json.dumps({"run_ts": "20260331_000000", "mode": "demo"}, ensure_ascii=True))
    _write(root / "case_manifest_20260331_000000.json", json.dumps({"run_ts": "20260331_000000", "stage_outputs": ["Verification_20260331"]}, ensure_ascii=True))
    _write(root / "Meta" / "pipeline_summary_20260331_000000.md", "# Pipeline Summary\n\n- OK\n")
    _write(root / "Verification_20260331" / "verify_top10_20260331.txt", "Verification summary\nKeyword: orchard lane\n")
    _write(root / "Verification_20260331" / "verify_hits_20260331.csv", "source_id,preview\nverification,orchard lane\n")
    if with_ai:
        _write(root / "AI_Review_20260331" / "triage_summary.md", "# AI Review Triage Summary\n\n- Start with verification.\n")
    return root


def test_build_review_workspace_snapshot(tmp_path: Path) -> None:
    root = _build_case_root(tmp_path, "case-a")

    workspace = dashboard.build_review_workspace_snapshot(root, "orchard lane")

    assert workspace is not None
    assert workspace["question"] == "orchard lane"
    assert workspace["summary"]["case_root_name"] == "case-a"
    assert workspace["evidence_refs"]
    assert any(item["source_id"] == "review_index" for item in workspace["evidence_refs"])


def test_build_start_here_steps_prioritizes_review_spine() -> None:
    summary = {
        "resources": {
            "review_index": "review_index.md",
            "verification_preview": "Verification_20260331/verify_top10.txt",
            "ai_triage_summary": "AI_Review_20260331/triage_summary.md",
        }
    }

    steps = dashboard.build_start_here_steps(
        summary,
        has_operator_brief=False,
        has_compare_candidates=True,
    )

    titles = [step["title"] for step in steps]
    assert titles[0] == "Open the review index first"
    assert titles[1] == "Check the verification preview next"
    assert "Use the evidence ladder to choose the next artifact" in titles
    assert "Use AI quick view as a summary layer, not as ground truth" in titles
    assert titles[-1] == "Only compare after the current case makes sense"
