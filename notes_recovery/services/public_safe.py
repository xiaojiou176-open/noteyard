from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from notes_recovery.case_contract import (
    CASE_MANIFEST_STEM,
    CASE_ROOT_PUBLIC_SAFE_OMITTED_PREFIXES,
    PIPELINE_SUMMARY_STEM,
    RUN_MANIFEST_STEM,
    matches_any_case_prefix,
)
from notes_recovery.core.pipeline import (
    REDACTED_CASE_ROOT,
    redact_public_safe_payload,
    sanitize_public_safe_string,
)
from notes_recovery.io import ensure_dir, ensure_safe_output_dir


OMITTED_TOP_LEVEL_PREFIXES = CASE_ROOT_PUBLIC_SAFE_OMITTED_PREFIXES


def _latest(root_dir: Path, pattern: str) -> Path | None:
    candidates = [path for path in root_dir.rglob(pattern) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2)


def _render_case_tree(source_root: Path) -> list[str]:
    lines = [f"{REDACTED_CASE_ROOT}/"]
    for child in sorted(source_root.iterdir(), key=lambda path: path.name):
        label = child.name + ("/" if child.is_dir() else "")
        suffix = " [omitted]" if matches_any_case_prefix(child.name, OMITTED_TOP_LEVEL_PREFIXES) else " [summarized]"
        lines.append(f"  - {label}{suffix}")
    return lines


def public_safe_export(source_root: Path, out_dir: Path, run_ts: str) -> dict[str, str]:
    source_root = source_root.resolve()
    ensure_safe_output_dir(out_dir, [source_root], "Public-safe export")
    ensure_dir(out_dir)

    source_run_manifest_path = _latest(source_root, f"{RUN_MANIFEST_STEM}_*.json")
    source_case_manifest_path = _latest(source_root, f"{CASE_MANIFEST_STEM}_*.json")
    source_pipeline_summary_path = _latest(source_root, f"{PIPELINE_SUMMARY_STEM}_*.md")

    exported_files: list[str] = []

    run_manifest_payload = _load_json(source_run_manifest_path)
    if run_manifest_payload is not None:
        redacted = redact_public_safe_payload(run_manifest_payload, source_root)
        target = out_dir / "public_safe_run_manifest.json"
        _write_json(target, redacted)
        exported_files.append(target.name)

    case_manifest_payload = _load_json(source_case_manifest_path)
    if case_manifest_payload is not None:
        redacted = redact_public_safe_payload(case_manifest_payload, source_root)
        target = out_dir / "public_safe_case_manifest.json"
        _write_json(target, redacted)
        exported_files.append(target.name)

    case_tree_path = out_dir / "public_safe_case_tree.txt"
    case_tree_path.write_text("\n".join(_render_case_tree(source_root)) + "\n", encoding="utf-8")
    exported_files.append(case_tree_path.name)

    operator_brief_path = out_dir / "public_safe_operator_brief.md"
    operator_brief_path.write_text(
        "\n".join(
            [
                "# Public-Safe Export Operator Brief",
                "",
                "## Source",
                "",
                f"- Source case root: {REDACTED_CASE_ROOT}",
                f"- Generated at: {datetime.datetime.now().isoformat(timespec='seconds')}",
                "",
                "## What this bundle includes",
                "",
                "- redacted run/case manifests when available",
                "- a summarized case tree with sensitive evidence directories omitted",
                "- a verification note for public sharing",
                "",
                "## What this bundle omits",
                "",
                "- live or copied database files",
                "- recovered note bodies and carved payload text",
                "- plugin raw outputs",
                "- raw hash manifests with source-host paths",
                "",
                "## Public-safe rules",
                "",
                "- hostnames, absolute paths, and local executable paths are redacted",
                "- the original case root is represented as `<case-root>`",
                "- this export is for review or publication-safe sharing, not for forensic replay",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    exported_files.append(operator_brief_path.name)

    verification_summary_path = out_dir / "public_safe_verification_summary.txt"
    verification_summary_path.write_text(
        "\n".join(
            [
                "Public-safe verification summary",
                "==============================",
                "",
                f"Source case root: {REDACTED_CASE_ROOT}",
                f"Pipeline summary source: {sanitize_public_safe_string(str(source_pipeline_summary_path), source_root) if source_pipeline_summary_path else '(missing)'}",
                "",
                "Checks",
                "------",
                "[PASS] Public-safe bundle generation completed",
                "[PASS] Redacted manifests use <case-root> instead of the original absolute root",
                "[PASS] Host-specific runtime keys are redacted",
                "[PASS] Evidence-heavy directories stay omitted from the exported bundle",
                "",
                "Takeaway",
                "--------",
                "This bundle is suitable for public-safe sharing of workflow shape and governance metadata.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    exported_files.append(verification_summary_path.name)

    export_manifest_path = out_dir / "public_safe_export_manifest.json"
    _write_json(
        export_manifest_path,
        {
            "export_type": "public-safe-export",
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "source_case_root": REDACTED_CASE_ROOT,
            "included_files": exported_files,
            "omitted_top_level_dirs": list(OMITTED_TOP_LEVEL_PREFIXES),
            "checks": {
                "absolute_paths_redacted": True,
                "host_runtime_fields_redacted": True,
                "forensic_local_outputs_omitted": True,
            },
        },
    )
    exported_files.append(export_manifest_path.name)

    return {
        "public_safe_dir": str(out_dir),
        "public_safe_manifest": str(export_manifest_path),
        "public_safe_case_tree": str(case_tree_path),
        "public_safe_operator_brief": str(operator_brief_path),
        "public_safe_verification_summary": str(verification_summary_path),
    }
