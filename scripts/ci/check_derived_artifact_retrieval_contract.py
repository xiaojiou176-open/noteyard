from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from notes_recovery.services.case_protocol import derived_artifact_retrieval_contract


CONTRACT_FILE = "DERIVED_ARTIFACT_RETRIEVAL_CONTRACT.md"
INTEGRATION_TOKENS = {
    "notes_recovery/services/ask_case.py": (
        "select_case_evidence(",
        "build_evidence_ref(",
        "build_suggested_target(",
    ),
    "notes_recovery/services/ai_review.py": (
        "select_case_evidence(",
        "derived_artifact_retrieval_contract(",
        "build_artifact_priority_items(",
        "normalize_artifact_priority_items(",
    ),
    "notes_recovery/mcp/server.py": (
        "derived_artifact_retrieval_contract(",
        "inspect_case_artifact",
        "inspect_case_resource(",
        "select_case_evidence(",
        "build_evidence_ref(",
    ),
}


def _read(repo_root: Path) -> str:
    path = repo_root / CONTRACT_FILE
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _read_optional(repo_root: Path, relpath: str) -> str:
    try:
        return (repo_root / relpath).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def collect_derived_artifact_retrieval_contract_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []
    text = _read(repo_root)
    if not text:
        return [f"missing {CONTRACT_FILE}"]

    contract = derived_artifact_retrieval_contract()
    version = contract["version"]
    if version not in text:
        errors.append(f"{CONTRACT_FILE} is missing the current contract version: {version}")

    primary_retrieval_unit = contract["primary_retrieval_unit"]
    if primary_retrieval_unit not in text:
        errors.append(
            f"{CONTRACT_FILE} is missing the primary retrieval unit token: {primary_retrieval_unit}"
        )

    for field in contract["evidence_ref_fields"]:
        if f"`{field}`" not in text and field not in text:
            errors.append(f"{CONTRACT_FILE} is missing evidence-ref field: {field}")

    for artifact in contract["allowed_artifacts"]:
        source_id = artifact["source_id"]
        if f"`{source_id}`" not in text and source_id not in text:
            errors.append(f"{CONTRACT_FILE} is missing allowed artifact token: {source_id}")

    for exclusion in contract["absolute_exclusions"]:
        if exclusion not in text:
            errors.append(f"{CONTRACT_FILE} is missing exclusion token: {exclusion}")

    for token in ("notes-recovery case-diff", "notes-recovery plugins-validate"):
        if token not in text:
            errors.append(f"{CONTRACT_FILE} is missing adjacency token: {token}")

    for relpath, tokens in INTEGRATION_TOKENS.items():
        source = _read_optional(repo_root, relpath)
        if not source:
            errors.append(f"missing integration file: {relpath}")
            continue
        for token in tokens:
            if token not in source:
                errors.append(f"{relpath} is missing retrieval integration token: {token}")

    return errors


def main() -> int:
    errors = collect_derived_artifact_retrieval_contract_errors(REPO_ROOT)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("derived artifact retrieval contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
