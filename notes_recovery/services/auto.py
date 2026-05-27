from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from notes_recovery.case_contract import (
    CASE_DIR_DB_BACKUP,
    CASE_DIR_PROTOBUF_OUTPUT,
    CASE_DIR_QUERY_OUTPUT,
    CASE_DIR_QUERY_OUTPUT_RECOVERED,
    CASE_DIR_RECOVERED_BLOBS,
    CASE_DIR_RECOVERED_BLOBS_RECOVERED,
    CASE_DIR_RECOVERED_DB,
    CASE_DIR_SPOTLIGHT_ANALYSIS,
    CASE_DIR_VERIFICATION,
    CASE_FILE_NOTESTORE_SQLITE,
    case_dir,
    prefixed_case_dir,
)
from notes_recovery.core.pipeline import (
    PipelineStage,
    assert_pipeline_ok,
    build_timestamped_dir,
    build_timestamped_file,
    collect_snapshot_hash_targets,
    finalize_pipeline,
    run_pipeline,
    timestamp_now,
    write_hash_manifest,
)
from notes_recovery.core.text_bundle import generate_text_bundle
from notes_recovery.models import WalAction
from notes_recovery.services.carve import carve_gzip
from notes_recovery.services.flatten import flatten_backup
from notes_recovery.services.plugins import run_plugins
from notes_recovery.services.protobuf import parse_notes_protobuf
from notes_recovery.services.query import query_notes
from notes_recovery.services.recover import sqlite_recover
from notes_recovery.services.report import generate_report
from notes_recovery.services.snapshot import snapshot, warn_if_notes_running
from notes_recovery.services.spotlight import parse_spotlight_deep
from notes_recovery.services.verify import verify_hits
from notes_recovery.services.wal import wal_isolate


def auto_run(
    out_dir: Path,
    keyword: Optional[str],
    include_core_spotlight: bool,
    include_notes_cache: bool,
    run_wal: bool,
    run_query: bool,
    run_carve: bool,
    run_recover: bool,
    recover_ignore_freelist: bool,
    recover_lost_and_found: str,
    run_plugins_flag: bool,
    plugins_config: Optional[Path],
    plugins_enable_all: bool,
    generate_html_report: bool,
    report_out: Optional[Path],
    report_max_items: int,
    carve_max_hits: int,
    carve_window_size: int,
    carve_min_text_len: int,
    carve_min_text_ratio: float,
    run_protobuf: bool,
    protobuf_max_notes: int,
    protobuf_max_zdata_mb: int,
    run_spotlight_parse: bool,
    spotlight_parse_max_files: int,
    spotlight_parse_max_bytes: int,
    spotlight_parse_min_string_len: int,
    spotlight_parse_max_string_chars: int,
    spotlight_parse_max_rows: int,
    run_verify: bool,
    verify_top_n: int,
    verify_preview_len: int,
    verify_out: Optional[Path],
    verify_deep: bool,
    verify_deep_max_mb: int,
    verify_deep_max_hits_per_file: int,
    verify_deep_all: bool,
    verify_match_all: bool,
    verify_fuzzy: bool,
    verify_fuzzy_threshold: float,
    verify_fuzzy_boost: float,
    verify_fuzzy_max_len: int,
    run_ts_override: Optional[str] = None,
) -> None:
    warn_if_notes_running()
    run_ts = run_ts_override or timestamp_now()
    candidate_root = out_dir.parent / f"{out_dir.name}_{run_ts}"
    root_dir = candidate_root if candidate_root.exists() else build_timestamped_dir(out_dir, run_ts)
    print(f"Timestamped output directory: {root_dir}")
    db_dir = case_dir(root_dir, CASE_DIR_DB_BACKUP)
    db_path = db_dir / CASE_FILE_NOTESTORE_SQLITE
    recovered_db_path: Optional[Path] = None
    flat_dir: Optional[Path] = None

    pipeline_config = {
        "out_dir": str(out_dir),
        "root_dir": str(root_dir),
        "keyword": keyword,
        "include_core_spotlight": include_core_spotlight,
        "include_notes_cache": include_notes_cache,
        "run_wal": run_wal,
        "run_query": run_query,
        "run_carve": run_carve,
        "run_recover": run_recover,
        "recover_ignore_freelist": recover_ignore_freelist,
        "recover_lost_and_found": recover_lost_and_found,
        "run_plugins": run_plugins_flag,
        "plugins_config": str(plugins_config) if plugins_config else None,
        "plugins_enable_all": plugins_enable_all,
        "generate_html_report": generate_html_report,
        "report_out": str(report_out) if report_out else None,
        "report_max_items": report_max_items,
        "carve_max_hits": carve_max_hits,
        "carve_window_size": carve_window_size,
        "carve_min_text_len": carve_min_text_len,
        "carve_min_text_ratio": carve_min_text_ratio,
        "run_protobuf": run_protobuf,
        "protobuf_max_notes": protobuf_max_notes,
        "protobuf_max_zdata_mb": protobuf_max_zdata_mb,
        "run_spotlight_parse": run_spotlight_parse,
        "spotlight_parse_max_files": spotlight_parse_max_files,
        "spotlight_parse_max_bytes": spotlight_parse_max_bytes,
        "spotlight_parse_min_string_len": spotlight_parse_min_string_len,
        "spotlight_parse_max_string_chars": spotlight_parse_max_string_chars,
        "spotlight_parse_max_rows": spotlight_parse_max_rows,
        "run_verify": run_verify,
        "verify_top_n": verify_top_n,
        "verify_preview_len": verify_preview_len,
        "verify_out": str(verify_out) if verify_out else None,
        "verify_deep": verify_deep,
        "verify_deep_max_mb": verify_deep_max_mb,
        "verify_deep_max_hits_per_file": verify_deep_max_hits_per_file,
        "verify_deep_all": verify_deep_all,
        "verify_match_all": verify_match_all,
        "verify_fuzzy": verify_fuzzy,
        "verify_fuzzy_threshold": verify_fuzzy_threshold,
        "verify_fuzzy_boost": verify_fuzzy_boost,
        "verify_fuzzy_max_len": verify_fuzzy_max_len,
    }

    def stage_snapshot() -> dict[str, Any]:
        snapshot(root_dir, include_core_spotlight, include_notes_cache, run_ts)
        if not db_path.exists():
            raise RuntimeError(f"Database copy not found in snapshot: {db_path}")
        outputs = {
            "db_dir": str(db_dir),
            "db_path": str(db_path),
        }
        snapshot_manifest = root_dir / f"snapshot_hashes_{run_ts}.csv"
        if snapshot_manifest.exists():
            outputs["snapshot_hash_manifest"] = str(snapshot_manifest)
        return outputs

    def stage_recover() -> dict[str, Any]:
        nonlocal recovered_db_path
        recovered_db_path = sqlite_recover(
            db_path,
            case_dir(root_dir, CASE_DIR_RECOVERED_DB),
            recover_ignore_freelist,
            recover_lost_and_found,
        )
        return {"recovered_db": str(recovered_db_path)}

    def stage_plugins() -> dict[str, Any]:
        config_path = plugins_config or (root_dir / "plugins.json")
        run_plugins(root_dir, db_path, config_path, plugins_enable_all, run_ts)
        return {"plugins_config": str(config_path)}

    def stage_wal() -> dict[str, Any]:
        wal_isolate(db_dir, WalAction.ISOLATE, "WAL_Isolation", allow_original=False)
        wal_manifest = write_hash_manifest(
            root_dir,
            run_ts,
            collect_snapshot_hash_targets(root_dir),
            "wal",
        )
        return {
            "wal_isolation": str(db_dir / "WAL_Isolation"),
            "wal_manifest": str(wal_manifest) if wal_manifest else "",
        }

    def stage_query() -> dict[str, Any]:
        query_dir = case_dir(root_dir, CASE_DIR_QUERY_OUTPUT)
        outputs = {"query_dir": str(query_dir)}
        query_notes(db_path, keyword, query_dir, run_ts)
        if recovered_db_path:
            query_recovered_dir = case_dir(root_dir, CASE_DIR_QUERY_OUTPUT_RECOVERED)
            outputs["query_recovered_dir"] = str(query_recovered_dir)
            query_notes(recovered_db_path, keyword, query_recovered_dir, run_ts)
        return outputs

    def stage_carve() -> dict[str, Any]:
        carve_dir = case_dir(root_dir, CASE_DIR_RECOVERED_BLOBS)
        outputs = {"carve_dir": str(carve_dir)}
        carve_gzip(
            db_path,
            carve_dir,
            keyword,
            carve_max_hits,
            carve_window_size,
            carve_min_text_len,
            carve_min_text_ratio,
        )
        if recovered_db_path:
            carve_recovered_dir = case_dir(root_dir, CASE_DIR_RECOVERED_BLOBS_RECOVERED)
            outputs["carve_recovered_dir"] = str(carve_recovered_dir)
            carve_gzip(
                recovered_db_path,
                carve_recovered_dir,
                keyword,
                carve_max_hits,
                carve_window_size,
                carve_min_text_len,
                carve_min_text_ratio,
            )
        return outputs

    def stage_protobuf() -> dict[str, Any]:
        manifest = parse_notes_protobuf(
            db_path,
            case_dir(root_dir, CASE_DIR_PROTOBUF_OUTPUT),
            keyword,
            protobuf_max_notes,
            protobuf_max_zdata_mb,
            run_ts,
        )
        return {"protobuf_manifest": str(manifest)}

    def stage_spotlight_parse() -> dict[str, Any]:
        outputs = parse_spotlight_deep(
            root_dir,
            case_dir(root_dir, CASE_DIR_SPOTLIGHT_ANALYSIS),
            spotlight_parse_max_files,
            spotlight_parse_max_bytes,
            spotlight_parse_min_string_len,
            spotlight_parse_max_string_chars,
            spotlight_parse_max_rows,
            run_ts,
        )
        return outputs

    def stage_report() -> dict[str, Any]:
        report_path = report_out or (root_dir / f"report_{run_ts}.html")
        if report_out:
            report_path = build_timestamped_file(report_path, run_ts)
        generate_report(root_dir, keyword, report_path, report_max_items)
        print(f"Report generated: {report_path}")
        return {"report_path": str(report_path)}

    def stage_verify() -> dict[str, Any]:
        if not keyword:
            raise RuntimeError("A keyword is required when one-shot verification is enabled.")
        verify_out_dir = verify_out or prefixed_case_dir(root_dir, CASE_DIR_VERIFICATION, run_ts)
        if verify_out:
            verify_out_dir = build_timestamped_dir(verify_out_dir, run_ts)
        verify_hits(
            root_dir,
            keyword,
            verify_top_n,
            verify_preview_len,
            verify_out_dir,
            deep=verify_deep,
            deep_max_mb=verify_deep_max_mb,
            deep_max_hits_per_file=verify_deep_max_hits_per_file,
            match_all=verify_match_all,
            fuzzy=verify_fuzzy,
            fuzzy_threshold=verify_fuzzy_threshold,
            fuzzy_boost=verify_fuzzy_boost,
            fuzzy_max_len=verify_fuzzy_max_len,
            run_ts=run_ts,
            deep_all=verify_deep_all,
        )
        return {"verify_dir": str(verify_out_dir)}

    def stage_flatten() -> dict[str, Any]:
        nonlocal flat_dir
        flat_dir = root_dir.with_name(f"{root_dir.name}_Flat")
        flatten_backup(root_dir, flat_dir, True, run_ts)
        print(f"Flattened backup generated: {flat_dir}")
        return {"flat_dir": str(flat_dir)}

    def stage_bundle() -> dict[str, Any]:
        outputs = {"bundle_root": str(generate_text_bundle(root_dir, run_ts, keyword))}
        if flat_dir and flat_dir.exists():
            outputs["bundle_flat"] = str(generate_text_bundle(flat_dir, run_ts, keyword))
        return outputs

    stages = [
        PipelineStage("snapshot", True, True, stage_snapshot),
        PipelineStage("recover", False, run_recover, stage_recover),
        PipelineStage("protobuf-parse", False, run_protobuf, stage_protobuf),
        PipelineStage("spotlight-parse", False, run_spotlight_parse, stage_spotlight_parse),
        PipelineStage("plugins", False, run_plugins_flag, stage_plugins),
        PipelineStage("wal-isolate", False, run_wal, stage_wal),
        PipelineStage("query", False, run_query, stage_query),
        PipelineStage("carve-gzip", False, run_carve, stage_carve),
        PipelineStage("report", False, generate_html_report, stage_report),
        PipelineStage("verify", False, run_verify, stage_verify),
        PipelineStage("flatten", True, True, stage_flatten),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]

    stage_results = run_pipeline(stages)
    finalize_pipeline(root_dir, run_ts, "auto", pipeline_config, stage_results)
    assert_pipeline_ok(stage_results)


# =============================================================================
