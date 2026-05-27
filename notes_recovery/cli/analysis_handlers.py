from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from notes_recovery.case_contract import (
    CASE_DIR_PROTOBUF_OUTPUT,
    CASE_DIR_QUERY_OUTPUT,
    CASE_DIR_SPOTLIGHT_ANALYSIS,
    CASE_DIR_TIMELINE,
    case_dir,
)
from notes_recovery.models import ExitCode, PipelineStage


def handle_query_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    query_notes: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
    default_output_root: str,
) -> int:
    run_ts = timestamp_now()
    if args.out:
        base_out = resolve_path(args.out)
        out_dir = build_timestamped_dir(base_out, run_ts)
        run_root = out_dir
    else:
        run_root = build_timestamped_dir(resolve_path(default_output_root), run_ts)
        out_dir = case_dir(run_root, CASE_DIR_QUERY_OUTPUT)
    setup_cli_logging(args, run_ts, run_root, "query")
    print(f"Timestamped output directory: {out_dir}")
    db_path = resolve_path(args.db)

    def stage_query() -> dict[str, Any]:
        query_notes(db_path, args.keyword, out_dir, run_ts)
        return {"db_path": str(db_path), "query_dir": str(out_dir)}

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(out_dir, run_ts, args.keyword))}

    stages = [
        PipelineStage("query", True, True, stage_query),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "db_path": str(db_path),
        "keyword": args.keyword,
        "out_dir": str(out_dir),
    }
    finalize_pipeline(run_root, run_ts, "query", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_protobuf_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    parse_notes_protobuf: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
    default_output_root: str,
) -> int:
    run_ts = timestamp_now()
    if args.out:
        base_out = resolve_path(args.out)
        out_dir = build_timestamped_dir(base_out, run_ts)
        run_root = out_dir
    else:
        run_root = build_timestamped_dir(resolve_path(default_output_root), run_ts)
        out_dir = case_dir(run_root, CASE_DIR_PROTOBUF_OUTPUT)
    setup_cli_logging(args, run_ts, run_root, "protobuf")
    print(f"Timestamped output directory: {out_dir}")
    db_path = resolve_path(args.db)

    def stage_protobuf() -> dict[str, Any]:
        manifest = parse_notes_protobuf(
            db_path,
            out_dir,
            args.keyword,
            args.max_notes,
            args.max_zdata_mb,
            run_ts,
        )
        return {"db_path": str(db_path), "protobuf_manifest": str(manifest)}

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(out_dir, run_ts, args.keyword))}

    stages = [
        PipelineStage("protobuf-parse", True, True, stage_protobuf),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "db_path": str(db_path),
        "keyword": args.keyword,
        "max_notes": args.max_notes,
        "max_zdata_mb": args.max_zdata_mb,
        "out_dir": str(out_dir),
    }
    finalize_pipeline(run_root, run_ts, "protobuf", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_timeline_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    build_timeline: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
    timeline_strategy_version: str,
) -> int:
    root_dir = resolve_path(args.dir)
    run_ts = timestamp_now()
    base_out = resolve_path(args.out) if args.out else case_dir(root_dir, CASE_DIR_TIMELINE)
    out_dir = build_timestamped_dir(base_out, run_ts)
    setup_cli_logging(args, run_ts, out_dir, "timeline")
    print(f"Timestamped output directory: {out_dir}")

    def stage_timeline() -> dict[str, Any]:
        outputs = build_timeline(
            root_dir,
            out_dir,
            args.keyword,
            args.max_notes,
            args.max_events,
            args.spotlight_max_files,
            not args.no_fs,
            not args.no_plotly,
            run_ts,
        )
        outputs["root_dir"] = str(root_dir)
        return outputs

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(out_dir, run_ts, args.keyword))}

    stages = [
        PipelineStage("timeline", True, True, stage_timeline),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "root_dir": str(root_dir),
        "keyword": args.keyword,
        "max_notes": args.max_notes,
        "max_events": args.max_events,
        "spotlight_max_files": args.spotlight_max_files,
        "include_fs": not args.no_fs,
        "enable_plotly": not args.no_plotly,
        "out_dir": str(out_dir),
        "strategy_version": timeline_strategy_version,
    }
    finalize_pipeline(out_dir, run_ts, "timeline", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_spotlight_parse_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    parse_spotlight_deep: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
    spotlight_strategy_version: str,
) -> int:
    root_dir = resolve_path(args.dir)
    run_ts = timestamp_now()
    base_out = resolve_path(args.out) if args.out else case_dir(root_dir, CASE_DIR_SPOTLIGHT_ANALYSIS)
    out_dir = build_timestamped_dir(base_out, run_ts)
    setup_cli_logging(args, run_ts, out_dir, "spotlight-parse")
    print(f"Timestamped output directory: {out_dir}")

    def stage_spotlight() -> dict[str, Any]:
        outputs = parse_spotlight_deep(
            root_dir,
            out_dir,
            args.max_files,
            args.max_bytes,
            args.min_string_len,
            args.max_string_chars,
            args.max_rows_per_table,
            run_ts,
        )
        outputs["root_dir"] = str(root_dir)
        return outputs

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(out_dir, run_ts, None))}

    stages = [
        PipelineStage("spotlight-parse", True, True, stage_spotlight),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "root_dir": str(root_dir),
        "max_files": args.max_files,
        "max_bytes": args.max_bytes,
        "min_string_len": args.min_string_len,
        "max_string_chars": args.max_string_chars,
        "max_rows_per_table": args.max_rows_per_table,
        "strategy_version": spotlight_strategy_version,
        "out_dir": str(out_dir),
    }
    finalize_pipeline(out_dir, run_ts, "spotlight-parse", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value
