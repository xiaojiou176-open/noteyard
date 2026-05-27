from __future__ import annotations

import json
from pathlib import Path

import pytest

from notes_recovery.services import ai_review


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
        json.dumps({"root_dir": str(root), "stage_outputs": [str(root / "Verification_20260331")], "hash_manifests": []}, ensure_ascii=True),
    )
    _write(root / "Meta" / "pipeline_summary_20260331_000000.md", "# Pipeline Summary\n\n- OK\n")
    _write(
        root / "Verification_20260331" / "verify_top10_20260331_000000.txt",
        "Keyword: orchard\nTotal hits: 3\n#1 score=10 source=CSV file=Query_Output/demo.csv\n",
    )
    _write(
        root / "Verification_20260331" / "verify_hits_20260331_000000.csv",
        "source,source_detail,file,row,score,occ,keyword_hits,coverage,fuzzy_ratio,length,source_weight,preview\nCSV,Query_Output,demo.csv,1,10,1,1,1.0,0.0,20,1.2,orchard lane\n",
    )
    _write(
        root / "Timeline_20260331" / "timeline_summary_20260331_000000.json",
        json.dumps({"by_source": {"DB": 2}}, ensure_ascii=True),
    )
    _write(root / "report_20260331_000000.html", "<html><body><h1>Apple Notes Recovery Report</h1><p>offline review surface</p></body></html>")
    _write(root / "Text_Bundle_20260331" / "inventory_20260331_000000.md", "# File Inventory\n\n- Files: 10\n")
    return root


def _build_demo_resources(repo_root: Path) -> None:
    demo_root = repo_root / "notes_recovery" / "resources" / "demo"
    demo_root.mkdir(parents=True, exist_ok=True)
    _write(demo_root / "sanitized-case-tree.txt", "<case-root>/\n  - Verification_20260331/ [summarized]\n")
    _write(demo_root / "sanitized-verification-summary.txt", "Verification summary\nMatched keyword: orchard lane\nTop hit count: 3\n")
    _write(demo_root / "sanitized-operator-brief.md", "# Operator brief\n- Recovery stayed copy-first\n")


def test_build_ai_review_context_uses_derived_artifacts_only(tmp_path: Path) -> None:
    root = _build_case_root(tmp_path)

    context = ai_review.build_ai_review_context(root_dir=root, demo=False, repo_root=tmp_path)

    assert context["guardrails"]["derived_output_first"] is True
    assert context["guardrails"]["raw_evidence_included"] is False
    assert "review_index.md" in context["input_sources"]
    assert context["retrieval_contract"]["primary_retrieval_unit"] == "one-case-root-at-a-time"
    assert context["input_evidence_refs"]
    assert context["input_evidence_refs"][0]["selection_reason"]
    serialized = json.dumps(context, ensure_ascii=True)
    assert all("DB_Backup" not in path for path in context["input_sources"])
    assert "DB_Backup" not in json.dumps(context["artifacts"], ensure_ascii=True)
    assert "verify_top10_20260331_000000.txt" in serialized


def test_build_ai_review_context_keeps_large_json_artifacts_parseable(tmp_path: Path) -> None:
    root = _build_case_root(tmp_path)
    large_manifest = {
        "root_dir": str(root),
        "runtime": {
            "cwd": str(root),
            "long_note": "orchard lane " * 4000,
        },
        "stages": [],
    }
    _write(
        root / "run_manifest_20260331_000000.json",
        json.dumps(large_manifest, ensure_ascii=True),
    )

    context = ai_review.build_ai_review_context(root_dir=root, demo=False, repo_root=tmp_path)

    assert context["artifacts"]["run_manifest"] is not None
    assert context["artifacts"]["run_manifest"]["root_dir"] == "<case-root>"
    assert "runtime" in context["artifacts"]["run_manifest"]
    assert context["artifacts"]["run_manifest"]["runtime"]["long_note"].endswith("...")


def test_resolve_provider_config_requires_ollama_model(monkeypatch) -> None:
    monkeypatch.delenv("NOTES_AI_PROVIDER", raising=False)
    monkeypatch.delenv("NOTES_AI_OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("NOTES_AI_MODEL", raising=False)

    with pytest.raises(RuntimeError):
        ai_review.resolve_provider_config(
            provider="ollama",
            model=None,
            demo=False,
            ollama_base_url=None,
            openai_api_key=None,
            allow_cloud=False,
            timeout_sec=30,
        )


def test_run_ai_review_demo_with_mock_provider(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _build_demo_resources(repo_root)
    out_dir = tmp_path / "out"

    outputs = ai_review.run_ai_review(
        root_dir=None,
        out_dir=out_dir,
        run_ts="20260331_010000",
        provider="mock",
        model=None,
        demo=True,
        repo_root=repo_root,
        ollama_base_url=None,
        timeout_sec=30,
    )

    assert Path(outputs["triage_summary"]).exists()
    assert Path(outputs["top_findings"]).exists()
    assert Path(outputs["next_questions"]).exists()
    assert Path(outputs["artifact_priority"]).exists()
    priorities = json.loads(Path(outputs["artifact_priority"]).read_text(encoding="utf-8"))
    manifest = json.loads(Path(outputs["ai_review_manifest"]).read_text(encoding="utf-8"))
    assert manifest["provider"] == "mock"
    assert "derived-output-first" in manifest["safe_rules"]
    assert manifest["retrieval_contract_version"] == "2026-04-02.v1"
    assert manifest["input_evidence_refs"]
    assert priorities
    assert priorities[0]["source_id"]
    assert priorities[0]["tier"]
    assert priorities[0]["relpath"]
    assert priorities[0]["kind"]


def test_run_ai_review_updates_existing_review_index(tmp_path: Path) -> None:
    root = _build_case_root(tmp_path)

    original_call = ai_review._call_ollama

    try:
        ai_review._call_ollama = lambda **_kwargs: {  # type: ignore[assignment]
            "response": json.dumps(
                {
                    "summary": "Triage text",
                    "top_findings": [
                        {
                            "title": "Review the verification preview first",
                            "signal_strength": "high",
                            "evidence": "It is the fastest operator-facing signal.",
                        }
                    ],
                    "next_questions": ["What should a human inspect first?"],
                    "artifact_priority": [
                        {
                            "artifact": "verification_preview",
                            "priority": 1,
                            "reason": "Fastest signal",
                        }
                    ],
                },
                ensure_ascii=True,
            )
        }

        outputs = ai_review.run_ai_review(
            root_dir=root,
            out_dir=root / "AI_Review_20260331_020000",
            run_ts="20260331_020000",
            provider="ollama",
            model="llama3.1:8b",
            demo=False,
            repo_root=tmp_path,
            ollama_base_url=None,
            timeout_sec=30,
        )
    finally:
        ai_review._call_ollama = original_call  # type: ignore[assignment]

    review_index = (root / "review_index.md").read_text(encoding="utf-8")
    priorities = json.loads(Path(outputs["artifact_priority"]).read_text(encoding="utf-8"))
    assert "## AI Review" in review_index
    assert Path(outputs["triage_summary"]).name in review_index
    assert priorities[0]["source_id"] == "verification_preview"
    assert priorities[0]["tier"] == "tier_a_anchor"
    assert priorities[0]["relpath"].startswith("Verification_")


def test_resolve_provider_config_requires_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("NOTES_AI_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ai_review.resolve_provider_config(
            provider="openai",
            model="gpt-4.1-mini",
            demo=False,
            ollama_base_url=None,
            openai_api_key=None,
            allow_cloud=True,
            timeout_sec=30,
        )


def test_resolve_provider_config_requires_explicit_cloud_opt_in() -> None:
    with pytest.raises(RuntimeError, match="allow-cloud"):
        ai_review.resolve_provider_config(
            provider="openai",
            model="gpt-4.1-mini",
            demo=False,
            ollama_base_url=None,
            openai_api_key="test-key",
            allow_cloud=False,
            timeout_sec=30,
        )
