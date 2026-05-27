from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

import notes_recovery.config as config
from notes_recovery.cli.analysis_handlers import handle_timeline_command
from notes_recovery.cli.tail_handlers import (
    handle_public_safe_export_command,
    handle_report_command,
    handle_verify_command,
)
from notes_recovery.core.pipeline import (
    assert_pipeline_ok,
    build_timestamped_dir,
    build_timestamped_file,
    finalize_pipeline,
    run_pipeline,
    timestamp_now,
)
from notes_recovery.core.text_bundle import generate_text_bundle
from notes_recovery.io import resolve_path
from notes_recovery.mcp.registry import CaseRegistry, DEMO_RESOURCE_MAP, read_resource_text
from notes_recovery.mcp.server_resources import register_read_only_surfaces
from notes_recovery.mcp.server_tools import register_bounded_tools
from notes_recovery.services.ask_case import run_ask_case
from notes_recovery.services.case_protocol import (
    build_case_resource_lookup,
    build_demo_resources,
    build_evidence_ref,
    default_case_search_roots,
    derived_artifact_retrieval_contract,
    inspect_case_resource,
    select_case_evidence,
    summarize_case_root,
)
from notes_recovery.services.public_safe import public_safe_export
from notes_recovery.services.report import generate_report
from notes_recovery.services.timeline import build_timeline
from notes_recovery.services.verify import verify_hits

MCP_DEPENDENCY_HELP = (
    "The MCP server requires the optional MCP dependencies. "
    "Install `python -m pip install 'notes-recover[mcp]'` "
    "or `python -m pip install -e .[mcp]` first."
)


def _load_mcp_runtime():
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in runtime usage
        raise SystemExit(MCP_DEPENDENCY_HELP) from exc
    return FastMCP, ToolAnnotations


def _quiet_logging(*_args: Any, **_kwargs: Any) -> None:
    return None


def _run_quietly(func, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return func(*args, **kwargs)


def _select_case_evidence_payload(
    *,
    registry: CaseRegistry,
    retrieval_contract: dict[str, Any],
    case_id: str,
    question: str,
    max_results: int,
) -> dict[str, Any]:
    record = registry.require(case_id)
    resources = list(build_case_resource_lookup(record.root_dir, include_ai_review=True).values())
    evidence_items = select_case_evidence(
        resources,
        question,
        max_results=max_results,
    )
    return {
        "case_id": case_id,
        "question": question,
        "retrieval_contract_version": retrieval_contract["version"],
        "primary_retrieval_unit": retrieval_contract["primary_retrieval_unit"],
        "evidence_ref_schema_version": retrieval_contract["evidence_ref_schema_version"],
        "evidence_refs": [build_evidence_ref(item) for item in evidence_items],
    }


def _inspect_case_artifact_payload(
    *,
    registry: CaseRegistry,
    case_id: str,
    source_id: str,
) -> dict[str, Any]:
    record = registry.require(case_id)
    payload = inspect_case_resource(
        record.root_dir,
        source_id,
        include_ai_review=True,
    )
    payload["case_id"] = case_id
    return payload


def _run_verify_from_case(
    *,
    registry: CaseRegistry,
    case_id: str,
    keyword: str,
    top_n: int,
    preview_len: int,
) -> dict[str, Any]:
    record = registry.require(case_id)
    args = SimpleNamespace(
        dir=str(record.root_dir),
        out=None,
        keyword=keyword,
        top=top_n,
        preview_len=preview_len,
        no_deep=False,
        deep_max_mb=0,
        deep_max_hits_per_file=200,
        deep_core_only=False,
        match_all=False,
        no_fuzzy=False,
        fuzzy_threshold=0.72,
        fuzzy_boost=6.0,
        fuzzy_max_len=2000,
    )
    exit_code = _run_quietly(
        handle_verify_command,
        args,
        resolve_path=resolve_path,
        timestamp_now=timestamp_now,
        build_timestamped_dir=build_timestamped_dir,
        setup_cli_logging=_quiet_logging,
        verify_hits=verify_hits,
        generate_text_bundle=generate_text_bundle,
        run_pipeline=run_pipeline,
        finalize_pipeline=finalize_pipeline,
        assert_pipeline_ok=assert_pipeline_ok,
    )
    if exit_code != 0:
        raise RuntimeError("Verify command failed from MCP.")
    summary = summarize_case_root(record.root_dir, include_ai_review=True)
    return {"exit_code": exit_code, "case_id": case_id, "resources": summary["resources"]}


def _run_report_from_case(
    *,
    registry: CaseRegistry,
    case_id: str,
    keyword: str | None,
    max_items: int,
) -> dict[str, Any]:
    record = registry.require(case_id)
    args = SimpleNamespace(
        dir=str(record.root_dir),
        out=None,
        keyword=keyword,
        max_items=max_items,
    )
    exit_code = _run_quietly(
        handle_report_command,
        args,
        resolve_path=resolve_path,
        timestamp_now=timestamp_now,
        build_timestamped_file=build_timestamped_file,
        setup_cli_logging=_quiet_logging,
        generate_report=generate_report,
        generate_text_bundle=generate_text_bundle,
        run_pipeline=run_pipeline,
        finalize_pipeline=finalize_pipeline,
        assert_pipeline_ok=assert_pipeline_ok,
    )
    if exit_code != 0:
        raise RuntimeError("Report command failed from MCP.")
    summary = summarize_case_root(record.root_dir, include_ai_review=True)
    return {"exit_code": exit_code, "case_id": case_id, "resources": summary["resources"]}


def _build_timeline_from_case(
    *,
    registry: CaseRegistry,
    case_id: str,
    keyword: str | None,
    max_notes: int,
    max_events: int,
    spotlight_max_files: int,
) -> dict[str, Any]:
    record = registry.require(case_id)
    args = SimpleNamespace(
        dir=str(record.root_dir),
        out=None,
        keyword=keyword,
        max_notes=max_notes,
        max_events=max_events,
        spotlight_max_files=spotlight_max_files,
        no_fs=False,
        no_plotly=True,
    )
    exit_code = _run_quietly(
        handle_timeline_command,
        args,
        resolve_path=resolve_path,
        timestamp_now=timestamp_now,
        build_timestamped_dir=build_timestamped_dir,
        setup_cli_logging=_quiet_logging,
        build_timeline=build_timeline,
        generate_text_bundle=generate_text_bundle,
        run_pipeline=run_pipeline,
        finalize_pipeline=finalize_pipeline,
        assert_pipeline_ok=assert_pipeline_ok,
        timeline_strategy_version=config.TIMELINE_STRATEGY_VERSION,
    )
    if exit_code != 0:
        raise RuntimeError("Timeline command failed from MCP.")
    summary = summarize_case_root(record.root_dir, include_ai_review=True)
    return {"exit_code": exit_code, "case_id": case_id, "resources": summary["resources"]}


def _public_safe_export_from_case(
    *,
    registry: CaseRegistry,
    case_id: str,
    out_dir: str | None,
) -> dict[str, Any]:
    record = registry.require(case_id)
    if out_dir is None:
        out_value = f"./output/public_safe_bundle_{case_id}"
    else:
        candidate = Path(out_dir)
        if candidate.is_absolute():
            raise ValueError("MCP public_safe_export only accepts a relative output directory.")
        out_value = out_dir
    args = SimpleNamespace(dir=str(record.root_dir), out=out_value)
    exit_code = _run_quietly(
        handle_public_safe_export_command,
        args,
        resolve_path=resolve_path,
        timestamp_now=timestamp_now,
        build_timestamped_dir=build_timestamped_dir,
        setup_cli_logging=_quiet_logging,
        public_safe_export=public_safe_export,
        run_pipeline=run_pipeline,
        assert_pipeline_ok=assert_pipeline_ok,
    )
    if exit_code != 0:
        raise RuntimeError("public-safe-export command failed from MCP.")
    out_root = resolve_path(out_value).parent
    latest = sorted(out_root.glob(f"{Path(out_value).name}_*"))
    latest_dir = latest[-1] if latest else None
    return {
        "exit_code": exit_code,
        "case_id": case_id,
        "public_safe_dir": str(latest_dir) if latest_dir else "",
    }


def build_mcp_server(
    *,
    repo_root: Path,
    case_dirs: Iterable[Path],
    cases_roots: Iterable[Path],
) -> FastMCP:
    FastMCP, ToolAnnotations = _load_mcp_runtime()
    registry = CaseRegistry.build(case_dirs, cases_roots)
    retrieval_contract = derived_artifact_retrieval_contract()
    server = FastMCP(
        "NotesRecover MCP",
        instructions=(
            "Read-mostly MCP server for copy-first Apple Notes recovery cases. "
            "Stay on derived review artifacts and bounded derived-output tools."
        ),
    )

    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    bounded_write = ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )

    register_read_only_surfaces(
        server=server,
        registry=registry,
        repo_root=repo_root,
        retrieval_contract=retrieval_contract,
        read_only=read_only,
        demo_resource_map=DEMO_RESOURCE_MAP,
        read_resource_text=read_resource_text,
        build_demo_resources=build_demo_resources,
        summarize_case_root=summarize_case_root,
        select_case_evidence_payload=lambda case_id, question, max_results=6: _select_case_evidence_payload(
            registry=registry,
            retrieval_contract=retrieval_contract,
            case_id=case_id,
            question=question,
            max_results=max_results,
        ),
        inspect_case_artifact_payload=lambda case_id, source_id: _inspect_case_artifact_payload(
            registry=registry,
            case_id=case_id,
            source_id=source_id,
        ),
        run_ask_case=run_ask_case,
    )
    register_bounded_tools(
        server=server,
        bounded_write=bounded_write,
        run_verify=lambda case_id, keyword, top_n=10, preview_len=300: _run_verify_from_case(
            registry=registry,
            case_id=case_id,
            keyword=keyword,
            top_n=top_n,
            preview_len=preview_len,
        ),
        run_report=lambda case_id, keyword=None, max_items=50: _run_report_from_case(
            registry=registry,
            case_id=case_id,
            keyword=keyword,
            max_items=max_items,
        ),
        build_timeline=lambda case_id, keyword=None, max_notes=200, max_events=2000, spotlight_max_files=100: _build_timeline_from_case(
            registry=registry,
            case_id=case_id,
            keyword=keyword,
            max_notes=max_notes,
            max_events=max_events,
            spotlight_max_files=spotlight_max_files,
        ),
        public_safe_export=lambda case_id, out_dir=None: _public_safe_export_from_case(
            registry=registry,
            case_id=case_id,
            out_dir=out_dir,
        ),
    )
    return server


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="notes-recovery-mcp",
        description="Read-mostly MCP server for copy-first Apple Notes recovery cases.",
    )
    parser.add_argument(
        "--case-dir",
        action="append",
        default=[],
        help="Explicit case root to expose (repeatable).",
    )
    parser.add_argument(
        "--cases-root",
        action="append",
        default=[],
        help="Parent directory to scan for case roots (repeatable). Defaults to ./output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    case_dirs = [Path(item) for item in args.case_dir]
    cases_roots = [Path(item) for item in args.cases_root] or default_case_search_roots()
    server = build_mcp_server(repo_root=repo_root, case_dirs=case_dirs, cases_roots=cases_roots)
    server.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
