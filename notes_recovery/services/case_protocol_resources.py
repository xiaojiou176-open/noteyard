from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import notes_recovery.config as config
from notes_recovery.case_contract import (
    CASE_DIR_AI_REVIEW,
    CASE_DIR_TEXT_BUNDLE,
    CASE_MANIFEST_STEM,
    PIPELINE_SUMMARY_STEM,
    RUN_MANIFEST_STEM,
)

from .case_protocol_contract import (
    CASE_RESOURCE_SPECS,
    DEMO_RESOURCE_SPECS,
    CaseResource,
    DERIVED_ARTIFACT_RETRIEVAL_CONTRACT_VERSION,
    PRIMARY_RETRIEVAL_UNIT,
    spec_for_resource,
)
from .case_protocol_redaction import (
    build_resource,
    latest_dir,
    latest_file,
    load_json_text,
    read_csv_rows,
    read_text,
)


def is_case_root(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    if (path / "review_index.md").exists():
        return True
    if any(path.glob(f"{RUN_MANIFEST_STEM}_*.json")):
        return True
    if any(path.glob(f"{CASE_MANIFEST_STEM}_*.json")):
        return True
    return False


def discover_case_roots(
    *,
    case_dirs: Iterable[Path] = (),
    search_roots: Iterable[Path] = (),
) -> list[Path]:
    candidates: dict[str, Path] = {}

    def add(path: Path) -> None:
        resolved = path.expanduser().resolve()
        if is_case_root(resolved):
            candidates[str(resolved)] = resolved

    for path in case_dirs:
        add(path)

    for root in search_roots:
        resolved_root = root.expanduser().resolve()
        if not resolved_root.exists():
            continue
        add(resolved_root)
        for pattern in (
            f"{RUN_MANIFEST_STEM}_*.json",
            f"{CASE_MANIFEST_STEM}_*.json",
            "review_index.md",
        ):
            for path in resolved_root.rglob(pattern):
                add(path.parent)

    return sorted(candidates.values(), key=str)


def build_case_resources(root_dir: Path, *, include_ai_review: bool = True) -> list[CaseResource]:
    root_dir = root_dir.expanduser().resolve()
    review_index = root_dir / "review_index.md"
    run_manifest = latest_file(root_dir, f"{RUN_MANIFEST_STEM}_*.json")
    case_manifest = latest_file(root_dir, f"{CASE_MANIFEST_STEM}_*.json")
    pipeline_summary = latest_file(root_dir, f"{PIPELINE_SUMMARY_STEM}_*.md")
    verification_preview = latest_file(root_dir, "verify_top*.txt")
    verification_hits = latest_file(root_dir, "verify_hits_*.csv")
    timeline_summary = latest_file(root_dir, "timeline_summary_*.json")
    timeline_events = latest_file(root_dir, "timeline_events_*.json")
    report_path = latest_file(root_dir, "report_*.html")
    text_bundle_dir = latest_dir(root_dir, CASE_DIR_TEXT_BUNDLE)
    inventory_path = latest_file(text_bundle_dir, "inventory_*.md") if text_bundle_dir else None
    ai_review_dir = latest_dir(root_dir, CASE_DIR_AI_REVIEW) if include_ai_review else None
    ai_triage = ai_review_dir / "triage_summary.md" if ai_review_dir else None
    ai_findings = ai_review_dir / "top_findings.md" if ai_review_dir else None
    ai_questions = ai_review_dir / "next_questions.md" if ai_review_dir else None

    maybe_resources = [
        build_resource(
            source_id="review_index",
            artifact="Review index",
            path=review_index if review_index.exists() else None,
            root_dir=root_dir,
            content=read_text(review_index if review_index.exists() else None, root_dir),
            kind="review_index",
        ),
        build_resource(
            source_id="run_manifest",
            artifact="Run manifest",
            path=run_manifest,
            root_dir=root_dir,
            content=load_json_text(run_manifest, root_dir),
            kind="run_manifest",
        ),
        build_resource(
            source_id="case_manifest",
            artifact="Case manifest",
            path=case_manifest,
            root_dir=root_dir,
            content=load_json_text(case_manifest, root_dir),
            kind="case_manifest",
        ),
        build_resource(
            source_id="pipeline_summary",
            artifact="Pipeline summary",
            path=pipeline_summary,
            root_dir=root_dir,
            content=read_text(pipeline_summary, root_dir),
            kind="pipeline_summary",
        ),
        build_resource(
            source_id="verification_preview",
            artifact="Verification preview",
            path=verification_preview,
            root_dir=root_dir,
            content=read_text(verification_preview, root_dir),
            kind="verification_preview",
        ),
        build_resource(
            source_id="timeline_summary",
            artifact="Timeline summary",
            path=timeline_summary,
            root_dir=root_dir,
            content=load_json_text(timeline_summary, root_dir),
            kind="timeline_summary",
        ),
        build_resource(
            source_id="timeline_events",
            artifact="Timeline events",
            path=timeline_events,
            root_dir=root_dir,
            content=load_json_text(timeline_events, root_dir),
            kind="timeline_events",
        ),
        build_resource(
            source_id="report_excerpt",
            artifact="HTML report excerpt",
            path=report_path,
            root_dir=root_dir,
            content=read_text(report_path, root_dir, html=True),
            kind="report_excerpt",
        ),
        build_resource(
            source_id="text_bundle_inventory",
            artifact="Text bundle inventory",
            path=inventory_path,
            root_dir=root_dir,
            content=read_text(inventory_path, root_dir),
            kind="text_bundle_inventory",
        ),
        build_resource(
            source_id="ai_triage_summary",
            artifact="AI triage summary",
            path=ai_triage if ai_triage and ai_triage.exists() else None,
            root_dir=root_dir,
            content=read_text(ai_triage if ai_triage and ai_triage.exists() else None, root_dir),
            kind="ai_triage_summary",
        ),
        build_resource(
            source_id="ai_top_findings",
            artifact="AI top findings",
            path=ai_findings if ai_findings and ai_findings.exists() else None,
            root_dir=root_dir,
            content=read_text(ai_findings if ai_findings and ai_findings.exists() else None, root_dir),
            kind="ai_top_findings",
        ),
        build_resource(
            source_id="ai_next_questions",
            artifact="AI next questions",
            path=ai_questions if ai_questions and ai_questions.exists() else None,
            root_dir=root_dir,
            content=read_text(ai_questions if ai_questions and ai_questions.exists() else None, root_dir),
            kind="ai_next_questions",
        ),
    ]
    resources = [item for item in maybe_resources if item is not None]
    resources.extend(read_csv_rows(verification_hits, root_dir))
    return resources


def build_demo_resources(repo_root: Path, *, include_ai_review: bool = True) -> list[CaseResource]:
    demo_dir = repo_root / "notes_recovery" / "resources" / "demo"
    root_dir = repo_root.resolve()
    resources: list[CaseResource] = []
    entries = [
        ("demo_case_tree", "sanitized-case-tree.txt"),
        ("demo_verification_summary", "sanitized-verification-summary.txt"),
        ("demo_operator_brief", "sanitized-operator-brief.md"),
    ]
    if include_ai_review:
        entries.append(("ai_triage_summary", "sanitized-ai-triage-summary.md"))
    for source_id, filename in entries:
        spec = spec_for_resource(
            {
                "source_id": source_id,
                "kind": source_id,
                "artifact": (
                    DEMO_RESOURCE_SPECS.get(source_id) or CASE_RESOURCE_SPECS[source_id]
                ).artifact,
            }
        )
        path = demo_dir / filename
        built = build_resource(
            source_id=spec.source_id,
            artifact=spec.artifact,
            path=path if path.exists() else None,
            root_dir=root_dir,
            content=read_text(path if path.exists() else None, root_dir),
            kind=spec.kind,
        )
        if built is not None:
            resources.append(built)
    return resources


def build_case_resource_lookup(
    root_dir: Path,
    *,
    include_ai_review: bool = True,
) -> dict[str, CaseResource]:
    return {
        item.source_id: item
        for item in build_case_resources(root_dir, include_ai_review=include_ai_review)
    }


def describe_case_resources(resources: Iterable[CaseResource]) -> list[dict[str, Any]]:
    described: list[dict[str, Any]] = []
    for item in resources:
        spec = spec_for_resource(item)
        described.append(
            {
                "source_id": item.source_id,
                "artifact": item.artifact,
                "relpath": item.relpath,
                "kind": item.kind,
                "tier": spec.tier,
            }
        )
    return described


def summarize_case_root(root_dir: Path, *, include_ai_review: bool = True) -> dict[str, Any]:
    root_dir = root_dir.expanduser().resolve()
    resources = build_case_resources(root_dir, include_ai_review=include_ai_review)
    resource_paths = {item.source_id: item.relpath for item in resources}
    return {
        "retrieval_contract_version": DERIVED_ARTIFACT_RETRIEVAL_CONTRACT_VERSION,
        "primary_retrieval_unit": PRIMARY_RETRIEVAL_UNIT,
        "case_root_name": root_dir.name,
        "case_root": str(root_dir),
        "resource_count": len(resources),
        "resources": resource_paths,
        "resource_items": describe_case_resources(resources),
    }


def inspect_case_resource(
    root_dir: Path,
    source_id: str,
    *,
    include_ai_review: bool = True,
) -> dict[str, Any]:
    lookup = build_case_resource_lookup(root_dir, include_ai_review=include_ai_review)
    if source_id not in lookup:
        raise KeyError(source_id)
    resource = lookup[source_id]
    spec = spec_for_resource(resource)
    return {
        "source_id": resource.source_id,
        "artifact": resource.artifact,
        "relpath": resource.relpath,
        "kind": resource.kind,
        "tier": spec.tier,
        "mode": spec.mode,
        "selection_reason": spec.default_selection_reason,
        "excerpt": resource.excerpt,
        "content": resource.content,
        "retrieval_contract_version": DERIVED_ARTIFACT_RETRIEVAL_CONTRACT_VERSION,
        "primary_retrieval_unit": PRIMARY_RETRIEVAL_UNIT,
    }


def default_case_search_roots() -> list[Path]:
    return [config.DEFAULT_OUTPUT_ROOT.parent]


__all__ = [
    "build_case_resource_lookup",
    "build_case_resources",
    "build_demo_resources",
    "default_case_search_roots",
    "describe_case_resources",
    "discover_case_roots",
    "inspect_case_resource",
    "is_case_root",
    "summarize_case_root",
]
