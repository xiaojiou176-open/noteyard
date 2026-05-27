from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Iterable

from notes_recovery.case_contract import (
    CASE_DIR_AI_REVIEW,
    CASE_MANIFEST_STEM,
    CASE_DIR_TEXT_BUNDLE,
    PIPELINE_SUMMARY_STEM,
    RUN_MANIFEST_STEM,
)
from notes_recovery.io import ensure_dir
from notes_recovery.models import StageResult, StageStatus


def _latest_file(root_dir: Path, pattern: str) -> Path | None:
    candidates = [path for path in root_dir.rglob(pattern) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _latest_dir(root_dir: Path, prefix: str) -> Path | None:
    candidates = [
        path
        for path in root_dir.iterdir()
        if path.is_dir() and path.name.startswith(prefix)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _rel(root_dir: Path, path: Path | None) -> str:
    if path is None:
        return "Not generated in this run."
    try:
        return str(path.relative_to(root_dir))
    except Exception:
        return str(path)


def _stage_map(stage_results: Iterable[StageResult]) -> dict[str, StageResult]:
    return {item.name: item for item in stage_results}


AI_REVIEW_START = "<!-- AI_REVIEW_START -->"
AI_REVIEW_END = "<!-- AI_REVIEW_END -->"


def _render_ai_review_section(root_dir: Path, ai_review_dir: Path | None) -> list[str]:
    triage_path = ai_review_dir / "triage_summary.md" if ai_review_dir else None
    findings_path = ai_review_dir / "top_findings.md" if ai_review_dir else None
    questions_path = ai_review_dir / "next_questions.md" if ai_review_dir else None
    priority_path = ai_review_dir / "artifact_priority.json" if ai_review_dir else None

    return [
        AI_REVIEW_START,
        "## AI Review",
        "",
        "Use this section only after you intentionally run `notes-recovery ai-review`.",
        "The AI review reads review artifacts first. It does not make the local case root public and it should not be treated as forensic ground truth.",
        "",
        f"- Latest AI review directory: `{_rel(root_dir, ai_review_dir)}`",
        f"- Triage summary: `{_rel(root_dir, triage_path)}`",
        f"- Top findings: `{_rel(root_dir, findings_path)}`",
        f"- Next questions: `{_rel(root_dir, questions_path)}`",
        f"- Artifact priority: `{_rel(root_dir, priority_path)}`",
        AI_REVIEW_END,
    ]


def update_review_index_ai_section(root_dir: Path, ai_review_dir: Path) -> Path | None:
    review_index_path = root_dir / "review_index.md"
    if not review_index_path.exists():
        return None

    text = review_index_path.read_text(encoding="utf-8")
    rendered = "\n".join(_render_ai_review_section(root_dir, ai_review_dir))
    pattern = re.compile(
        rf"{re.escape(AI_REVIEW_START)}.*?{re.escape(AI_REVIEW_END)}",
        re.DOTALL,
    )
    if pattern.search(text):
        updated = pattern.sub(rendered, text)
    else:
        if not text.endswith("\n"):
            text += "\n"
        updated = text + "\n" + rendered + "\n"
    review_index_path.write_text(updated, encoding="utf-8")
    return review_index_path


def generate_review_index(
    root_dir: Path,
    run_ts: str,
    mode: str,
    stage_results: list[StageResult],
) -> Path:
    ensure_dir(root_dir)
    review_index_path = root_dir / "review_index.md"

    stage_lookup = _stage_map(stage_results)
    run_manifest = _latest_file(root_dir, f"{RUN_MANIFEST_STEM}_*.json")
    case_manifest = _latest_file(root_dir, f"{CASE_MANIFEST_STEM}_*.json")
    pipeline_summary = _latest_file(root_dir, f"{PIPELINE_SUMMARY_STEM}_*.md")
    report_path = _latest_file(root_dir, "report_*.html")
    verification_preview = _latest_file(root_dir, "verify_top*.txt")
    verification_csv = _latest_file(root_dir, "verify_hits_*.csv")
    timeline_summary = _latest_file(root_dir, "timeline_summary_*.json")
    timeline_events = _latest_file(root_dir, "timeline_events_*.json")
    text_bundle_dir = _latest_dir(root_dir, CASE_DIR_TEXT_BUNDLE)
    ai_review_dir = _latest_dir(root_dir, CASE_DIR_AI_REVIEW)

    start_here: list[str] = [
        "1. Read the pipeline summary first so you know which stages ran and which ones failed or were skipped.",
        "2. Open the verification preview next if you want the fastest hit-oriented view.",
        "3. Open the HTML report when you want a richer scan across query, carve, and plugin results.",
        "4. Use the timeline outputs when chronology matters more than keyword hits.",
        "5. Use the text bundle when you want review-friendly copies instead of raw mixed outputs.",
        "6. Create a public-safe bundle only when you need a shareable view outside the local forensic environment.",
    ]

    if verification_preview is None:
        start_here[1] = "2. Verification was not generated in this run, so jump from the pipeline summary to the HTML report or text bundle."
    if report_path is None:
        start_here[2] = "3. Report output was not generated in this run, so use verification or the text bundle as your human-readable entry."
    if timeline_summary is None and timeline_events is None:
        start_here[3] = "4. Timeline output was not generated in this run, so treat chronology as unavailable until you run `timeline`."

    lines = [
        "# Review Index",
        "",
        "This file is a navigation layer for operators.",
        "It does not replace the underlying artifacts, and it does not create a new truth source.",
        "",
        "## Run Context",
        "",
        f"- Mode: `{mode}`",
        f"- Run timestamp: `{run_ts}`",
        f"- Generated at: `{datetime.datetime.now().isoformat(timespec='seconds')}`",
        f"- Run manifest: `{_rel(root_dir, run_manifest)}`",
        f"- Case manifest: `{_rel(root_dir, case_manifest)}`",
        f"- Pipeline summary: `{_rel(root_dir, pipeline_summary)}`",
        "",
        "## Start Here",
        "",
        *[f"- {item}" for item in start_here],
        "",
        "## Surface Guide",
        "",
        "| Surface | What it is for | Current file or directory |",
        "| --- | --- | --- |",
        f"| Verification preview | Fast Top-N hit scan for likely matches | `{_rel(root_dir, verification_preview)}` |",
        f"| Verification CSV | Full verification hit table for sorting/filtering later | `{_rel(root_dir, verification_csv)}` |",
        f"| HTML report | Richer offline review surface across query, carve, and plugins | `{_rel(root_dir, report_path)}` |",
        f"| Timeline summary | Chronology-first explanation of what happened and when | `{_rel(root_dir, timeline_summary)}` |",
        f"| Timeline events | Raw event export for deeper timeline inspection | `{_rel(root_dir, timeline_events)}` |",
        f"| Text bundle | Human-readable copies and previews of key outputs | `{_rel(root_dir, text_bundle_dir)}` |",
        f"| AI review | AI-assisted triage, findings, and next-step guidance | `{_rel(root_dir, ai_review_dir)}` |",
        "| Public-safe export | Shareable redacted bundle for review outside the local forensic environment | Run `notes-recovery public-safe-export --dir <case-root> --out ./output/public_safe_bundle` |",
        "",
        "## Stage Snapshot",
        "",
        "| Stage | Status | Why it matters |",
        "| --- | --- | --- |",
    ]

    for stage_name in (
        "snapshot",
        "recover",
        "query",
        "carve-gzip",
        "report",
        "verify",
        "flatten",
        "text-bundle",
    ):
        result = stage_lookup.get(stage_name)
        if result is None:
            lines.append(f"| {stage_name} | not-run | This stage was not part of the current run. |")
            continue
        if result.status == StageStatus.OK:
            note = "Generated outputs are available for review."
        elif result.status == StageStatus.SKIPPED:
            note = result.skip_reason or "Skipped in this run."
        else:
            note = result.error or "Failed during this run."
        lines.append(f"| {stage_name} | {result.status.value} | {note} |")

    lines.extend(
        [
            "",
            "## Suggested Next Step",
            "",
            "- If you only need the fastest signal, start with the verification preview.",
            "- If you need narrative context, open the HTML report.",
            "- If you need review-friendly text copies, open the text bundle.",
            "- If an AI review exists, use it as an operator-facing summary of review artifacts rather than as forensic ground truth.",
            "- If you need to share the workflow shape safely, export a public-safe bundle instead of sending the local case root.",
            "",
        ]
    )

    lines.extend(["", *_render_ai_review_section(root_dir, ai_review_dir), ""])

    review_index_path.write_text("\n".join(lines), encoding="utf-8")
    return review_index_path
