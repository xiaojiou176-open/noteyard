from __future__ import annotations

from pathlib import Path

from notes_recovery import case_contract


def test_case_contract_path_helpers(tmp_path: Path) -> None:
    root = tmp_path / "case"
    run_ts = "20260101_000000"

    assert case_contract.run_manifest_path(root, run_ts) == root / f"run_manifest_{run_ts}.json"
    assert case_contract.case_manifest_path(root, run_ts) == root / f"case_manifest_{run_ts}.json"
    assert case_contract.pipeline_summary_path(root, run_ts) == root / "Meta" / f"pipeline_summary_{run_ts}.md"
    assert case_contract.prefixed_case_dir(root, case_contract.CASE_DIR_VERIFICATION, run_ts) == root / f"Verification_{run_ts}"


def test_case_contract_prefix_matching_handles_variants() -> None:
    assert case_contract.matches_case_prefix("Query_Output", case_contract.CASE_DIR_QUERY_OUTPUT)
    assert case_contract.matches_case_prefix("Query_Output_20260101", case_contract.CASE_DIR_QUERY_OUTPUT)
    assert case_contract.matches_case_prefix(
        case_contract.CASE_DIR_RECOVERED_BLOBS_RECOVERED,
        case_contract.CASE_DIR_RECOVERED_BLOBS,
    )
    assert not case_contract.matches_case_prefix("Reports", case_contract.CASE_DIR_RECOVERED_BLOBS)


def test_case_contract_public_safe_omission_covers_prefixed_surfaces() -> None:
    assert case_contract.matches_any_case_prefix(
        "Text_Bundle_20260101_000000",
        case_contract.CASE_ROOT_PUBLIC_SAFE_OMITTED_PREFIXES,
    )
    assert case_contract.matches_any_case_prefix(
        case_contract.CASE_DIR_RECOVERED_BLOBS_RECOVERED,
        case_contract.CASE_ROOT_PUBLIC_SAFE_OMITTED_PREFIXES,
    )
    assert case_contract.matches_any_case_prefix(
        "AI_Review_20260101_000000",
        case_contract.CASE_ROOT_PUBLIC_SAFE_OMITTED_PREFIXES,
    )
