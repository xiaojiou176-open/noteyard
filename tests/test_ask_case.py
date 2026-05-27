from __future__ import annotations

import json
from pathlib import Path

from notes_recovery.services import ai_review, ask_case


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_case_root(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    root.mkdir()
    _write(root / "review_index.md", "# Review Index\n\n- Start with verification.\n")
    _write(
        root / "run_manifest_20260331_000000.json",
        json.dumps({"root_dir": str(root), "runtime": {"cwd": str(root)}, "stages": []}, ensure_ascii=True),
    )
    _write(
        root / "case_manifest_20260331_000000.json",
        json.dumps({"root_dir": str(root), "stage_outputs": [str(root / "Verification_20260331")]}, ensure_ascii=True),
    )
    _write(root / "Meta" / "pipeline_summary_20260331_000000.md", "# Pipeline Summary\n\n- verification ran successfully\n")
    _write(
        root / "Verification_20260331" / "verify_top10_20260331_000000.txt",
        "Keyword: orchard lane\nTop hit: Query_Output/demo.csv row 1\n",
    )
    _write(
        root / "Verification_20260331" / "verify_hits_20260331_000000.csv",
        "source,source_detail,file,row,score,preview\nCSV,Query_Output,demo.csv,1,10,orchard lane and meeting note\n",
    )
    _write(
        root / "Timeline_20260331" / "timeline_summary_20260331_000000.json",
        json.dumps({"events": 2, "sources": {"DB": 1, "FS": 1}}, ensure_ascii=True),
    )
    _write(root / "report_20260331_000000.html", "<html><body><h1>Report</h1><p>orchard lane report excerpt</p></body></html>")
    _write(root / "Text_Bundle_20260331" / "inventory_20260331_000000.md", "# File Inventory\n\n- Files: 10\n")
    _write(
        root / "AI_Review_20260331_000000" / "triage_summary.md",
        "# AI Review Triage Summary\n\n- Start with the verification preview.\n",
    )
    _write(
        root / "AI_Review_20260331_000000" / "next_questions.md",
        "# AI Review Next Questions\n\n- Which hit should be checked first?\n",
    )
    return root


def _build_demo_resources(repo_root: Path) -> None:
    demo_root = repo_root / "notes_recovery" / "resources" / "demo"
    demo_root.mkdir(parents=True, exist_ok=True)
    _write(demo_root / "sanitized-case-tree.txt", "<case-root>/\n  - Verification_20260331/ [summarized]\n")
    _write(demo_root / "sanitized-verification-summary.txt", "Verification summary\nMatched keyword: orchard lane\n")
    _write(demo_root / "sanitized-operator-brief.md", "# Operator brief\n- Recovery stayed copy-first\n")
    _write(demo_root / "sanitized-ai-triage-summary.md", "# AI Review Triage Summary\n- Synthetic proof\n")


def test_run_ask_case_demo_with_mock_provider(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _build_demo_resources(repo_root)

    payload = ask_case.run_ask_case(
        root_dir=None,
        question="What should I inspect first?",
        demo=True,
        repo_root=repo_root,
        provider="mock",
        model=None,
    )

    assert payload["source_mode"] == "demo"
    assert payload["confidence"] in {"low", "medium", "high"}
    assert payload["evidence_refs"]
    assert payload["evidence_refs"][0]["relpath"]
    assert payload["evidence_refs"][0]["selection_reason"]
    assert payload["evidence_refs"][0]["kind"]
    assert payload["evidence_refs"][0]["locator"] is None
    assert "derived" in payload["answer"].lower() or "verification" in payload["answer"].lower()


def test_run_ask_case_case_root_with_stubbed_provider(tmp_path: Path) -> None:
    root = _build_case_root(tmp_path)
    original_call = ai_review._call_ollama

    try:
        ai_review._call_ollama = lambda **_kwargs: {  # type: ignore[assignment]
            "response": json.dumps(
                {
                    "answer": "The strongest lead is in the verification preview before you read the larger report surface.",
                    "confidence": "high",
                    "uncertainty": "Chronology still needs manual confirmation.",
                    "evidence_refs": [
                        {"source_id": "verification_preview", "reason": "It contains the fastest ranked hit."},
                        {"source_id": "review_index", "reason": "It explains the operator review order."},
                    ],
                    "suggested_next_targets": [
                        {"artifact": "Timeline summary", "reason": "Confirm chronology after the hit preview."}
                    ],
                },
                ensure_ascii=True,
            )
        }

        payload = ask_case.run_ask_case(
            root_dir=root,
            question="Which artifact should I inspect first for orchard lane?",
            demo=False,
            repo_root=tmp_path,
            provider="ollama",
            model="llama3.1:8b",
        )
    finally:
        ai_review._call_ollama = original_call  # type: ignore[assignment]

    assert payload["confidence"] == "high"
    assert len(payload["evidence_refs"]) == 2
    assert payload["evidence_refs"][0]["source_id"] == "verification_preview"
    assert payload["evidence_refs"][0]["path"].startswith("Verification_")
    assert payload["evidence_refs"][0]["relpath"] == payload["evidence_refs"][0]["path"]
    assert payload["evidence_refs"][0]["kind"] == "verification_preview"
    assert payload["evidence_refs"][0]["selection_reason"] == "It contains the fastest ranked hit."
    assert payload["evidence_refs"][0]["score"] > 0
    assert payload["evidence_refs"][0]["locator"] is None
    assert payload["suggested_next_targets"][0]["artifact"] == "Timeline summary"
