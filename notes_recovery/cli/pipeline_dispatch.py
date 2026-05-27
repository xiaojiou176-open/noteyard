from __future__ import annotations

from typing import Any, Mapping


def dispatch_pipeline_command(
    args,
    *,
    deps: Mapping[str, Any],
) -> int | None:
    if args.command == "snapshot":
        return deps["handle_snapshot_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            snapshot=deps["snapshot"],
            flatten_backup=deps["flatten_backup"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "wal-isolate":
        return deps["handle_wal_isolate_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            setup_cli_logging=deps["setup_cli_logging"],
            wal_isolate=deps["wal_isolate"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "wal-extract":
        return deps["handle_wal_extract_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            wal_extract=deps["wal_extract"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "wal-diff":
        return deps["handle_wal_diff_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            wal_diff=deps["wal_diff"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "freelist-carve":
        return deps["handle_freelist_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            freelist_carve=deps["freelist_carve"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "fsevents-correlate":
        return deps["handle_fsevents_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            correlate_fsevents_with_spotlight=deps["correlate_fsevents_with_spotlight"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "fts-index":
        return deps["handle_fts_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            build_fts_index=deps["build_fts_index"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "query":
        return deps["handle_query_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            query_notes=deps["query_notes"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
            default_output_root=str(deps["DEFAULT_OUTPUT_ROOT"]),
        )
    if args.command == "protobuf":
        return deps["handle_protobuf_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            parse_notes_protobuf=deps["parse_notes_protobuf"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
            default_output_root=str(deps["DEFAULT_OUTPUT_ROOT"]),
        )
    if args.command == "timeline":
        return deps["handle_timeline_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            build_timeline=deps["build_timeline"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
            timeline_strategy_version=deps["TIMELINE_STRATEGY_VERSION"],
        )
    if args.command == "spotlight-parse":
        return deps["handle_spotlight_parse_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            parse_spotlight_deep=deps["parse_spotlight_deep"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
            spotlight_strategy_version=deps["SPOTLIGHT_PARSE_STRATEGY_VERSION"],
        )
    if args.command == "plugins":
        return deps["handle_plugins_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            setup_cli_logging=deps["setup_cli_logging"],
            run_plugins=deps["run_plugins"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "flatten":
        return deps["handle_flatten_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            flatten_backup=deps["flatten_backup"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "auto":
        return deps["handle_auto_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            auto_run=deps["auto_run"],
        )
    return None
