from __future__ import annotations

import json
from pathlib import Path

from notes_recovery.services import case_diff


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_case_root(
    tmp_path: Path,
    *,
    name: str,
    run_ts: str,
    mode: str,
    verification_text: str = "Keyword: orchard lane\nTop hit: row 1\n",
    report_text: str = "<html><body><h1>Report</h1><p>Report excerpt</p></body></html>",
    include_timeline: bool = False,
    include_report: bool = False,
    include_ai_review: bool = False,
) -> Path:
    root = tmp_path / name
    root.mkdir()

    verification_dir = root / f"Verification_{run_ts}"
    text_bundle_dir = root / f"Text_Bundle_{run_ts}"
    stage_outputs = [str(verification_dir), str(text_bundle_dir)]
    stages = [
        {"name": "snapshot", "status": "ok"},
        {"name": "verify", "status": "ok"},
    ]

    if include_timeline:
        timeline_dir = root / f"Timeline_{run_ts}"
        stage_outputs.append(str(timeline_dir))
        stages.append({"name": "timeline", "status": "ok"})

    if include_report:
        stages.append({"name": "report", "status": "ok"})

    _write(root / "review_index.md", "# Review Index\n\n- Start with verification.\n")
    _write(
        root / f"run_manifest_{run_ts}.json",
        json.dumps(
            {
                "run_ts": run_ts,
                "mode": mode,
                "stages": stages,
            },
            ensure_ascii=True,
        ),
    )
    _write(
        root / f"case_manifest_{run_ts}.json",
        json.dumps(
            {
                "run_ts": run_ts,
                "stage_outputs": stage_outputs,
            },
            ensure_ascii=True,
        ),
    )
    _write(root / "Meta" / f"pipeline_summary_{run_ts}.md", "# Pipeline Summary\n\n- OK\n")
    _write(
        verification_dir / f"verify_top10_{run_ts}.txt",
        verification_text,
    )
    _write(
        verification_dir / f"verify_hits_{run_ts}.csv",
        "source,source_detail,file,row,score,preview\nCSV,Query_Output,demo.csv,1,10,orchard lane\n",
    )
    _write(text_bundle_dir / f"inventory_{run_ts}.md", "# File Inventory\n\n- Files: 2\n")

    if include_timeline:
        _write(
            root / f"Timeline_{run_ts}" / f"timeline_summary_{run_ts}.json",
            json.dumps({"events": 2, "sources": {"DB": 1, "FS": 1}}, ensure_ascii=True),
        )

    if include_report:
        _write(root / f"report_{run_ts}.html", report_text)

    if include_ai_review:
        ai_dir = root / f"AI_Review_{run_ts}"
        _write(ai_dir / "triage_summary.md", "# AI Review Triage Summary\n\n- Start with verification.\n")
        _write(ai_dir / "next_questions.md", "# AI Review Next Questions\n\n- Which hit first?\n")

    return root


def test_build_case_diff_payload_tracks_manifest_resource_and_surface_changes(tmp_path: Path) -> None:
    left = _build_case_root(
        tmp_path,
        name="case_left",
        run_ts="20260331_000000",
        mode="recover",
    )
    right = _build_case_root(
        tmp_path,
        name="case_right",
        run_ts="20260401_000000",
        mode="verify",
        include_timeline=True,
        include_report=True,
        include_ai_review=True,
    )

    payload = case_diff.build_case_diff_payload(left, right)

    assert payload["diff"]["has_differences"] is True
    assert payload["diff"]["resources"]["only_in_b"] == [
        "ai_next_questions",
        "ai_triage_summary",
        "report_excerpt",
        "timeline_summary",
    ]
    assert payload["diff"]["review_surfaces"]["timeline"] == {"a": False, "b": True}
    assert payload["diff"]["review_surfaces"]["report"] == {"a": False, "b": True}
    assert payload["diff"]["review_surfaces"]["ai_review"] == {"a": False, "b": True}
    assert payload["diff"]["manifests"]["run_manifest"]["fields_changed"] == [
        "run_ts",
        "mode",
        "stage_names",
        "stage_statuses",
    ]
    assert payload["diff"]["manifests"]["case_manifest"]["fields_changed"] == [
        "run_ts",
        "stage_output_surfaces",
        "stage_output_count",
    ]


def test_build_case_diff_payload_ignores_raw_resource_content_changes(tmp_path: Path) -> None:
    left = _build_case_root(
        tmp_path,
        name="case_left",
        run_ts="20260331_000000",
        mode="recover",
        verification_text="Keyword: orchard lane\nTop hit: row 1\n",
        report_text="<html><body><p>Left report wording</p></body></html>",
        include_report=True,
    )
    right = _build_case_root(
        tmp_path,
        name="case_right",
        run_ts="20260331_000000",
        mode="recover",
        verification_text="Keyword: orchard lane\nTop hit: row 9\nDifferent text body\n",
        report_text="<html><body><p>Right report wording</p></body></html>",
        include_report=True,
    )

    payload = case_diff.build_case_diff_payload(left, right)

    assert payload["diff"]["has_differences"] is False
    assert payload["diff"]["resources"]["only_in_a"] == []
    assert payload["diff"]["resources"]["only_in_b"] == []
    assert payload["diff"]["resources"]["path_changes"] == []
    assert payload["diff"]["manifests"]["run_manifest"]["fields_changed"] == []
    assert payload["diff"]["manifests"]["case_manifest"]["fields_changed"] == []
    assert "fingerprint" not in json.dumps(payload, ensure_ascii=True)


def test_build_case_diff_summary_is_repo_friendly(tmp_path: Path) -> None:
    left = _build_case_root(
        tmp_path,
        name="case_left",
        run_ts="20260331_000000",
        mode="recover",
    )
    right = _build_case_root(
        tmp_path,
        name="case_right",
        run_ts="20260401_000000",
        mode="verify",
        include_timeline=True,
    )

    payload = case_diff.build_case_diff_payload(left, right)
    summary = case_diff.build_case_diff_summary(payload)

    assert "Derived surfaces only" in summary
    assert "timeline" in summary
    assert "stage_output_surfaces" in summary
