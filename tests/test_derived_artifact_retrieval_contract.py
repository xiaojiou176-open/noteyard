from __future__ import annotations

from pathlib import Path

from notes_recovery.services.case_protocol import derived_artifact_retrieval_contract
from scripts.ci.check_derived_artifact_retrieval_contract import (
    collect_derived_artifact_retrieval_contract_errors,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _contract_text() -> str:
    contract = derived_artifact_retrieval_contract()
    lines = [
        f"Version: `{contract['version']}`",
        contract["primary_retrieval_unit"],
        "notes-recovery case-diff",
        "notes-recovery plugins-validate",
    ]
    lines.extend(f"`{field}`" for field in contract["evidence_ref_fields"])
    lines.extend(f"`{artifact['source_id']}`" for artifact in contract["allowed_artifacts"])
    lines.extend(contract["absolute_exclusions"])
    return "\n".join(lines) + "\n"


def _write_integration_files(tmp_path: Path) -> None:
    _write(
        tmp_path / "notes_recovery" / "services" / "ask_case.py",
        "def run_ask_case():\n"
        "    build_evidence_ref({})\n"
        "    build_suggested_target({})\n"
        "    return select_case_evidence([], '')\n",
    )
    _write(
        tmp_path / "notes_recovery" / "services" / "ai_review.py",
        "def run_ai_review():\n"
        "    build_artifact_priority_items([])\n"
        "    normalize_artifact_priority_items([], [])\n"
        "    select_case_evidence([], '')\n"
        "    return derived_artifact_retrieval_contract()\n",
    )
    _write(
        tmp_path / "notes_recovery" / "mcp" / "server.py",
        "def build_mcp_server():\n"
        "    inspect_case_resource('.', 'review_index')\n"
        "    select_case_evidence([], '')\n"
        "    build_evidence_ref({})\n"
        "    inspect_case_artifact = True\n"
        "    return derived_artifact_retrieval_contract()\n",
    )


def test_retrieval_contract_guard_passes_when_tokens_align(tmp_path: Path) -> None:
    _write(tmp_path / "DERIVED_ARTIFACT_RETRIEVAL_CONTRACT.md", _contract_text())
    _write_integration_files(tmp_path)

    assert collect_derived_artifact_retrieval_contract_errors(tmp_path) == []


def test_retrieval_contract_guard_detects_missing_artifact_token(tmp_path: Path) -> None:
    _write(
        tmp_path / "DERIVED_ARTIFACT_RETRIEVAL_CONTRACT.md",
        _contract_text().replace("`review_index`", "", 1),
    )
    _write_integration_files(tmp_path)

    errors = collect_derived_artifact_retrieval_contract_errors(tmp_path)
    assert any("review_index" in error for error in errors)


def test_retrieval_contract_guard_detects_missing_integration_token(tmp_path: Path) -> None:
    _write(tmp_path / "DERIVED_ARTIFACT_RETRIEVAL_CONTRACT.md", _contract_text())
    _write(
        tmp_path / "notes_recovery" / "services" / "ask_case.py",
        "def run_ask_case():\n    return select_case_evidence([],'')\n",
    )
    _write(
        tmp_path / "notes_recovery" / "services" / "ai_review.py",
        "def run_ai_review():\n    return derived_artifact_retrieval_contract()\n",
    )
    _write(
        tmp_path / "notes_recovery" / "mcp" / "server.py",
        "def build_mcp_server():\n    return derived_artifact_retrieval_contract()\n",
    )

    errors = collect_derived_artifact_retrieval_contract_errors(tmp_path)
    assert any("build_evidence_ref(" in error for error in errors)


def test_retrieval_contract_exposes_verification_hit_wildcard() -> None:
    contract = derived_artifact_retrieval_contract()
    assert any(
        artifact["source_id"] == "verification_hit_*"
        and artifact["kind"] == "verification_hit"
        for artifact in contract["allowed_artifacts"]
    )
