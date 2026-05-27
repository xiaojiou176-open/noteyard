from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from notes_recovery.case_contract import CASE_DIR_DB_BACKUP, CASE_FILE_NOTESTORE_SQLITE, case_dir
from notes_recovery.models import ExitCode, PipelineStage


def handle_plugins_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    setup_cli_logging: Callable[..., Any],
    run_plugins: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    root_dir = resolve_path(args.dir)
    db_path = resolve_path(args.db) if args.db else (case_dir(root_dir, CASE_DIR_DB_BACKUP) / CASE_FILE_NOTESTORE_SQLITE)
    config_path = resolve_path(args.config) if args.config else (root_dir / "plugins.json")
    run_ts = timestamp_now()
    setup_cli_logging(args, run_ts, root_dir, "plugins")

    def stage_plugins() -> dict[str, Any]:
        run_plugins(root_dir, db_path, config_path, args.enable_all, run_ts)
        return {
            "db_path": str(db_path),
            "config_path": str(config_path),
            "root_dir": str(root_dir),
        }

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(root_dir, run_ts, None))}

    stages = [
        PipelineStage("plugins", True, True, stage_plugins),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "db_path": str(db_path),
        "config_path": str(config_path),
        "enable_all": args.enable_all,
    }
    finalize_pipeline(root_dir, run_ts, "plugins", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_flatten_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    flatten_backup: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    run_ts = timestamp_now()
    src_dir = resolve_path(args.src)
    base_out = resolve_path(args.out)
    out_dir = build_timestamped_dir(base_out, run_ts)
    setup_cli_logging(args, run_ts, out_dir, "flatten")

    def stage_flatten() -> dict[str, Any]:
        flatten_backup(src_dir, out_dir, not args.no_manifest, run_ts)
        print(f"Flattened backup written: {out_dir}")
        return {"src_dir": str(src_dir), "out_dir": str(out_dir)}

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(out_dir, run_ts, None))}

    stages = [
        PipelineStage("flatten", True, True, stage_flatten),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "src_dir": str(src_dir),
        "out_dir": str(out_dir),
        "include_manifest": not args.no_manifest,
    }
    finalize_pipeline(out_dir, run_ts, "flatten", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_auto_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    auto_run: Callable[..., Any],
) -> int:
    run_ts = timestamp_now()
    base_out = resolve_path(args.out)
    expected_root = build_timestamped_dir(base_out, run_ts)
    setup_cli_logging(args, run_ts, expected_root, "auto")
    auto_run(
        base_out,
        args.keyword,
        not args.skip_core_spotlight,
        not args.skip_notes_cache,
        not args.skip_wal,
        not args.skip_query,
        not args.skip_carve,
        args.recover,
        args.recover_ignore_freelist,
        args.recover_lost_and_found,
        args.plugins,
        resolve_path(args.plugins_config) if args.plugins_config else None,
        args.plugins_enable_all,
        args.report,
        resolve_path(args.report_out) if args.report_out else None,
        args.report_max_items,
        args.carve_max_hits,
        args.carve_window_size,
        args.carve_min_text_len,
        args.carve_min_text_ratio,
        args.protobuf,
        args.protobuf_max_notes,
        args.protobuf_max_zdata_mb,
        args.spotlight_parse,
        args.spotlight_parse_max_files,
        args.spotlight_parse_max_bytes,
        args.spotlight_parse_min_string_len,
        args.spotlight_parse_max_string_chars,
        args.spotlight_parse_max_rows,
        args.verify,
        args.verify_top,
        args.verify_preview_len,
        resolve_path(args.verify_out) if args.verify_out else None,
        not args.verify_no_deep,
        args.verify_deep_max_mb,
        args.verify_deep_max_hits_per_file,
        not args.verify_deep_core_only,
        args.verify_match_all,
        not args.verify_no_fuzzy,
        args.verify_fuzzy_threshold,
        args.verify_fuzzy_boost,
        args.verify_fuzzy_max_len,
        run_ts_override=run_ts,
    )
    return ExitCode.OK.value
