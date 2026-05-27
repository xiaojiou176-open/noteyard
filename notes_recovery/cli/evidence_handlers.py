from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from notes_recovery.models import ExitCode, PipelineStage, WalAction


def handle_snapshot_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    snapshot: Callable[..., Any],
    flatten_backup: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    run_ts = timestamp_now()
    base_out = resolve_path(args.out)
    out_dir = build_timestamped_dir(base_out, run_ts)
    setup_cli_logging(args, run_ts, out_dir, "snapshot")
    print(f"Timestamped output directory: {out_dir}")
    flat_dir: Optional[Path] = None

    def stage_snapshot() -> dict[str, Any]:
        snapshot(out_dir, args.include_core_spotlight, args.include_notes_cache, run_ts)
        return {"snapshot_dir": str(out_dir)}

    def stage_flatten() -> dict[str, Any]:
        nonlocal flat_dir
        flat_dir = out_dir.with_name(f"{out_dir.name}_Flat")
        flatten_backup(out_dir, flat_dir, True, run_ts)
        print(f"Flattened export created: {flat_dir}")
        return {"flat_dir": str(flat_dir)}

    def stage_bundle() -> dict[str, Any]:
        outputs = {"bundle_root": str(generate_text_bundle(out_dir, run_ts, None))}
        if flat_dir:
            outputs["bundle_flat"] = str(generate_text_bundle(flat_dir, run_ts, None))
        return outputs

    stages = [
        PipelineStage("snapshot", True, True, stage_snapshot),
        PipelineStage("flatten", True, True, stage_flatten),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "out_dir": str(out_dir),
        "include_core_spotlight": args.include_core_spotlight,
        "include_notes_cache": args.include_notes_cache,
    }
    finalize_pipeline(out_dir, run_ts, "snapshot", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_wal_isolate_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    setup_cli_logging: Callable[..., Any],
    wal_isolate: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    run_ts = timestamp_now()
    action = WalAction(args.action)
    target_dir = resolve_path(args.dir)
    setup_cli_logging(args, run_ts, target_dir, "wal-isolate")
    isolate_dir = target_dir / args.isolate_dir

    def stage_wal() -> dict[str, Any]:
        wal_isolate(target_dir, action, args.isolate_dir, args.allow_original)
        return {
            "action": action.value,
            "target_dir": str(target_dir),
            "isolate_dir": str(isolate_dir),
        }

    stages = [PipelineStage("wal-isolate", True, True, stage_wal)]
    stage_results = run_pipeline(stages)
    config = {
        "action": action.value,
        "target_dir": str(target_dir),
        "isolate_dir": str(isolate_dir),
        "allow_original": args.allow_original,
    }
    finalize_pipeline(isolate_dir, run_ts, "wal-isolate", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_wal_extract_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    wal_extract: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    root_dir = resolve_path(args.dir)
    run_ts = timestamp_now()
    base_out = resolve_path(args.out) if args.out else (root_dir / "WAL_Extract")
    out_dir = build_timestamped_dir(base_out, run_ts)
    setup_cli_logging(args, run_ts, out_dir, "wal-extract")
    print(f"Timestamped output directory: {out_dir}")
    wal_path = resolve_path(args.wal) if args.wal else None

    def stage_wal_extract() -> dict[str, Any]:
        manifest = wal_extract(
            root_dir,
            out_dir,
            args.keyword,
            args.max_frames,
            args.page_size,
            args.dump_pages,
            args.dump_only_duplicates,
            args.strings,
            args.strings_min_len,
            args.strings_max_chars,
            run_ts,
            wal_path,
        )
        return {"wal_manifest": str(manifest)}

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(out_dir, run_ts, args.keyword))}

    stages = [
        PipelineStage("wal-extract", True, True, stage_wal_extract),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "root_dir": str(root_dir),
        "out_dir": str(out_dir),
        "wal": str(wal_path) if wal_path else "",
        "keyword": args.keyword,
        "max_frames": args.max_frames,
        "page_size": args.page_size,
        "dump_pages": args.dump_pages,
        "dump_only_duplicates": args.dump_only_duplicates,
        "strings": args.strings,
        "strings_min_len": args.strings_min_len,
        "strings_max_chars": args.strings_max_chars,
    }
    finalize_pipeline(out_dir, run_ts, "wal-extract", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_wal_diff_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    wal_diff: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    run_ts = timestamp_now()
    wal_a = resolve_path(args.wal_a)
    wal_b = resolve_path(args.wal_b)
    base_out = resolve_path(args.out) if args.out else (Path.cwd() / "WAL_Diff")
    out_dir = build_timestamped_dir(base_out, run_ts)
    setup_cli_logging(args, run_ts, out_dir, "wal-diff")
    print(f"Timestamped output directory: {out_dir}")

    def stage_wal_diff() -> dict[str, Any]:
        summary = wal_diff(wal_a, wal_b, out_dir, args.max_frames, args.page_size, run_ts)
        return {"wal_diff_summary": str(summary)}

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(out_dir, run_ts, None))}

    stages = [
        PipelineStage("wal-diff", True, True, stage_wal_diff),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "wal_a": str(wal_a),
        "wal_b": str(wal_b),
        "out_dir": str(out_dir),
        "page_size": args.page_size,
        "max_frames": args.max_frames,
    }
    finalize_pipeline(out_dir, run_ts, "wal-diff", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_freelist_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    freelist_carve: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    run_ts = timestamp_now()
    db_path = resolve_path(args.db)
    base_out = resolve_path(args.out) if args.out else (db_path.parent / "Freelist_Carve")
    out_dir = build_timestamped_dir(base_out, run_ts)
    setup_cli_logging(args, run_ts, out_dir, "freelist-carve")
    print(f"Timestamped output directory: {out_dir}")

    def stage_freelist() -> dict[str, Any]:
        meta = freelist_carve(
            db_path,
            out_dir,
            args.keyword,
            args.min_text_len,
            args.max_pages,
            args.max_output_mb,
            args.strings_max_chars,
            run_ts,
        )
        return {"freelist_meta": str(meta)}

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(out_dir, run_ts, args.keyword))}

    stages = [
        PipelineStage("freelist-carve", True, True, stage_freelist),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "db": str(db_path),
        "out_dir": str(out_dir),
        "keyword": args.keyword,
        "min_text_len": args.min_text_len,
        "max_pages": args.max_pages,
        "max_output_mb": args.max_output_mb,
        "strings_max_chars": args.strings_max_chars,
    }
    finalize_pipeline(out_dir, run_ts, "freelist-carve", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_fsevents_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    correlate_fsevents_with_spotlight: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    run_ts = timestamp_now()
    root_dir = resolve_path(args.dir) if args.dir else None
    fsevents_path = resolve_path(args.fsevents)
    spotlight_events = resolve_path(args.spotlight_events) if args.spotlight_events else None
    base_out = resolve_path(args.out) if args.out else (Path.cwd() / "FSEvents_Correlation")
    out_dir = build_timestamped_dir(base_out, run_ts)
    setup_cli_logging(args, run_ts, out_dir, "fsevents-correlate")
    print(f"Timestamped output directory: {out_dir}")

    def stage_fsevents() -> dict[str, Any]:
        return correlate_fsevents_with_spotlight(
            fsevents_path,
            root_dir,
            spotlight_events,
            out_dir,
            args.window_sec,
            args.max_records,
            run_ts,
        )

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(out_dir, run_ts, None))}

    stages = [
        PipelineStage("fsevents-correlate", True, True, stage_fsevents),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "root_dir": str(root_dir) if root_dir else "",
        "fsevents": str(fsevents_path),
        "spotlight_events": str(spotlight_events) if spotlight_events else "",
        "out_dir": str(out_dir),
        "window_sec": args.window_sec,
        "max_records": args.max_records,
    }
    finalize_pipeline(out_dir, run_ts, "fsevents-correlate", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_fts_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    build_fts_index: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    root_dir = resolve_path(args.dir)
    run_ts = timestamp_now()
    base_out = resolve_path(args.out) if args.out else (root_dir / "FTS_Index")
    out_dir = build_timestamped_dir(base_out, run_ts)
    setup_cli_logging(args, run_ts, out_dir, "fts-index")
    print(f"Timestamped output directory: {out_dir}")
    db_path = resolve_path(args.db) if args.db else None
    db_columns = [col.strip() for col in (args.db_columns or "").split(",") if col.strip()]

    def stage_fts() -> dict[str, Any]:
        fts_db_path = build_fts_index(
            root_dir,
            out_dir,
            args.keyword,
            args.source,
            db_path,
            args.db_table,
            db_columns,
            args.db_title_column,
            args.max_docs,
            args.max_file_mb,
            args.max_text_chars,
        )
        return {"fts_db": str(fts_db_path)}

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(out_dir, run_ts, args.keyword))}

    stages = [
        PipelineStage("fts-index", True, True, stage_fts),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "root_dir": str(root_dir),
        "out_dir": str(out_dir),
        "keyword": args.keyword,
        "source": args.source,
        "db": str(db_path) if db_path else "",
        "db_table": args.db_table or "",
        "db_columns": db_columns,
        "db_title_column": args.db_title_column or "",
        "max_docs": args.max_docs,
        "max_file_mb": args.max_file_mb,
        "max_text_chars": args.max_text_chars,
    }
    finalize_pipeline(out_dir, run_ts, "fts-index", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value
