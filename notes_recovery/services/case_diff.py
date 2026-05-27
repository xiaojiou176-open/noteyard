from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from notes_recovery.case_contract import CASE_ROOT_DERIVED_PREFIXES, matches_case_prefix
from notes_recovery.io import ensure_dir
from notes_recovery.services.case_protocol import build_case_resource_lookup, summarize_case_root

CASE_DIFF_VERSION = "2026-04-01.v2"
REVIEW_SURFACES = (
    ("review_index", {"review_index"}),
    ("pipeline_summary", {"pipeline_summary"}),
    ("verification", {"verification_preview"}),
    ("timeline", {"timeline_summary", "timeline_events"}),
    ("report", {"report_excerpt"}),
    ("text_bundle", {"text_bundle_inventory"}),
    ("ai_review", {"ai_triage_summary", "ai_top_findings", "ai_next_questions"}),
)


def _load_resource_json(resources: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    resource = resources.get(source_id)
    if resource is None:
        return None
    try:
        payload = json.loads(resource.content)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_stage_output_surface(value: Any) -> str:
    name = Path(str(value)).name.rstrip("/")
    for prefix in sorted(CASE_ROOT_DERIVED_PREFIXES, key=len, reverse=True):
        if matches_case_prefix(name, prefix):
            return prefix
    return name


def _summarize_run_manifest(resources: dict[str, Any]) -> dict[str, Any]:
    resource = resources.get("run_manifest")
    summary: dict[str, Any] = {
        "present": resource is not None,
        "path": resource.relpath if resource is not None else None,
        "run_ts": None,
        "mode": None,
        "stage_names": [],
        "stage_statuses": {},
    }
    payload = _load_resource_json(resources, "run_manifest")
    if payload is None:
        return summary

    stages = payload.get("stages")
    stage_names: list[str] = []
    stage_statuses: dict[str, Any] = {}
    if isinstance(stages, list):
        for item in stages:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name:
                continue
            stage_names.append(name)
            if "status" in item:
                stage_statuses[name] = item.get("status")

    summary.update(
        {
            "run_ts": payload.get("run_ts"),
            "mode": payload.get("mode"),
            "stage_names": stage_names,
            "stage_statuses": stage_statuses,
        }
    )
    return summary


def _summarize_case_manifest(resources: dict[str, Any]) -> dict[str, Any]:
    resource = resources.get("case_manifest")
    summary: dict[str, Any] = {
        "present": resource is not None,
        "path": resource.relpath if resource is not None else None,
        "run_ts": None,
        "stage_output_surfaces": [],
        "stage_output_count": 0,
    }
    payload = _load_resource_json(resources, "case_manifest")
    if payload is None:
        return summary

    stage_outputs = payload.get("stage_outputs")
    surfaces: list[str] = []
    if isinstance(stage_outputs, list):
        surfaces = sorted({_normalize_stage_output_surface(item) for item in stage_outputs})

    summary.update(
        {
            "run_ts": payload.get("run_ts"),
            "stage_output_surfaces": surfaces,
            "stage_output_count": len(stage_outputs) if isinstance(stage_outputs, list) else 0,
        }
    )
    return summary


def _review_surface_presence(resource_ids: set[str]) -> dict[str, bool]:
    presence: dict[str, bool] = {}
    for surface, required_ids in REVIEW_SURFACES:
        if surface == "verification":
            presence[surface] = "verification_preview" in resource_ids or any(
                source_id.startswith("verification_hit_") for source_id in resource_ids
            )
            continue
        presence[surface] = any(source_id in resource_ids for source_id in required_ids)
    return presence


def _build_case_snapshot(case_root: Path) -> dict[str, Any]:
    summary = summarize_case_root(case_root, include_ai_review=True)
    resources = build_case_resource_lookup(case_root, include_ai_review=True)
    resource_ids = set(summary["resources"])
    return {
        "case_root_name": summary["case_root_name"],
        "case_root": summary["case_root"],
        "resource_count": summary["resource_count"],
        "resources": summary["resources"],
        "review_surfaces": _review_surface_presence(resource_ids),
        "manifests": {
            "run_manifest": _summarize_run_manifest(resources),
            "case_manifest": _summarize_case_manifest(resources),
        },
    }


def _changed_fields(left: dict[str, Any], right: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if left.get(field) != right.get(field)]


def build_case_diff_payload(case_a: Path, case_b: Path) -> dict[str, Any]:
    case_a = case_a.expanduser().resolve()
    case_b = case_b.expanduser().resolve()
    snapshot_a = _build_case_snapshot(case_a)
    snapshot_b = _build_case_snapshot(case_b)

    resources_a = snapshot_a["resources"]
    resources_b = snapshot_b["resources"]
    shared_resource_ids = sorted(set(resources_a) & set(resources_b))
    path_changes = [
        {
            "source_id": source_id,
            "path_a": resources_a[source_id],
            "path_b": resources_b[source_id],
        }
        for source_id in shared_resource_ids
        if resources_a[source_id] != resources_b[source_id]
    ]

    review_surface_diff = {
        surface: {
            "a": snapshot_a["review_surfaces"][surface],
            "b": snapshot_b["review_surfaces"][surface],
        }
        for surface, _source_ids in REVIEW_SURFACES
    }

    run_manifest_changed = _changed_fields(
        snapshot_a["manifests"]["run_manifest"],
        snapshot_b["manifests"]["run_manifest"],
        ("present", "run_ts", "mode", "stage_names", "stage_statuses"),
    )
    case_manifest_changed = _changed_fields(
        snapshot_a["manifests"]["case_manifest"],
        snapshot_b["manifests"]["case_manifest"],
        ("present", "run_ts", "stage_output_surfaces", "stage_output_count"),
    )

    has_review_surface_changes = any(
        item["a"] != item["b"] for item in review_surface_diff.values()
    )

    diff = {
        "has_differences": any(
            (
                run_manifest_changed,
                case_manifest_changed,
                set(resources_a) - set(resources_b),
                set(resources_b) - set(resources_a),
                path_changes,
                has_review_surface_changes,
            )
        ),
        "manifests": {
            "run_manifest": {
                "a": snapshot_a["manifests"]["run_manifest"],
                "b": snapshot_b["manifests"]["run_manifest"],
                "fields_changed": run_manifest_changed,
            },
            "case_manifest": {
                "a": snapshot_a["manifests"]["case_manifest"],
                "b": snapshot_b["manifests"]["case_manifest"],
                "fields_changed": case_manifest_changed,
            },
        },
        "resources": {
            "only_in_a": sorted(set(resources_a) - set(resources_b)),
            "only_in_b": sorted(set(resources_b) - set(resources_a)),
            "path_changes": path_changes,
        },
        "review_surfaces": review_surface_diff,
    }

    return {
        "diff_version": CASE_DIFF_VERSION,
        "scope": "case-root-derived-surfaces",
        "case_a": snapshot_a,
        "case_b": snapshot_b,
        "diff": diff,
        "recommended_next_step": (
            "Start with manifest field changes, then review surfaces that only exist on one side, "
            "and only then inspect the newly available derived resources. "
            "This comparison intentionally avoids raw copied evidence and raw artifact body diffs."
        ),
    }


def build_case_diff_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# Case Diff Summary",
        "",
        "Derived surfaces only. This comparison stays on case manifests, derived resources, and review surface presence.",
        "It does not compare raw copied evidence content.",
        "",
        f"- Diff version: `{payload['diff_version']}`",
        f"- Case A: `{payload['case_a']['case_root_name']}`",
        f"- Case B: `{payload['case_b']['case_root_name']}`",
        f"- Differences detected: `{payload['diff']['has_differences']}`",
        "",
        "## Review Surface Presence",
        "",
        "| Surface | Case A | Case B |",
        "| --- | --- | --- |",
    ]

    for surface, _source_ids in REVIEW_SURFACES:
        surface_diff = payload["diff"]["review_surfaces"][surface]
        lines.append(
            f"| {surface} | {'yes' if surface_diff['a'] else 'no'} | {'yes' if surface_diff['b'] else 'no'} |"
        )

    lines.extend(
        [
            "",
            "## Manifest Differences",
            "",
            f"- Run manifest changed fields: {', '.join(payload['diff']['manifests']['run_manifest']['fields_changed']) or '(none)'}",
            f"- Case manifest changed fields: {', '.join(payload['diff']['manifests']['case_manifest']['fields_changed']) or '(none)'}",
            "",
            "## Resource Availability",
            "",
            f"- Only in A: {', '.join(payload['diff']['resources']['only_in_a']) or '(none)'}",
            f"- Only in B: {', '.join(payload['diff']['resources']['only_in_b']) or '(none)'}",
        ]
    )

    path_changes = payload["diff"]["resources"]["path_changes"]
    if path_changes:
        lines.append("- Path changes:")
        for item in path_changes:
            lines.append(
                f"  - {item['source_id']}: `{item['path_a']}` -> `{item['path_b']}`"
            )
    else:
        lines.append("- Path changes: (none)")

    lines.extend(
        [
            "",
            "## Recommended Next Step",
            "",
            payload["recommended_next_step"],
            "",
        ]
    )
    return "\n".join(lines)


def write_case_diff_outputs(out_dir: Path, payload: dict[str, Any]) -> dict[str, str]:
    ensure_dir(out_dir)
    json_path = out_dir / "case_diff.json"
    md_path = out_dir / "case_diff_summary.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    md_path.write_text(build_case_diff_summary(payload), encoding="utf-8")
    return {"json": str(json_path), "summary": str(md_path)}
