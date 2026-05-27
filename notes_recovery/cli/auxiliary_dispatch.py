from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


def dispatch_auxiliary_command(
    args,
    *,
    deps: Mapping[str, Any],
    repo_root: Path,
) -> int | None:
    if args.command == "ai-review":
        return deps["handle_ai_review_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            run_ai_review=deps["run_ai_review"],
        )
    if args.command == "ask-case":
        return deps["handle_ask_case_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            setup_cli_logging=deps["setup_cli_logging"],
            run_ask_case=deps["run_ask_case"],
        )
    if args.command == "doctor":
        return deps["handle_doctor_command"](
            args,
            timestamp_now=deps["timestamp_now"],
            setup_cli_logging=deps["setup_cli_logging"],
            run_doctor=deps["run_doctor"],
        )
    if args.command == "plugins-validate":
        return deps["handle_plugins_validate_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            setup_cli_logging=deps["setup_cli_logging"],
            validate_plugins_config=deps["validate_plugins_config"],
            render_plugins_validation_report=deps["render_plugins_validation_report"],
        )
    if args.command == "case-diff":
        return deps["handle_case_diff_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            build_case_diff_payload=deps["build_case_diff_payload"],
            write_case_diff_outputs=deps["write_case_diff_outputs"],
        )
    if args.command == "demo":
        return deps["handle_demo_command"](
            args,
            timestamp_now=deps["timestamp_now"],
            setup_cli_logging=deps["setup_cli_logging"],
            repo_root=repo_root,
        )
    if args.command == "public-safe-export":
        return deps["handle_public_safe_export_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            public_safe_export=deps["public_safe_export"],
            run_pipeline=deps["run_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "report":
        return deps["handle_report_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_file=deps["build_timestamped_file"],
            setup_cli_logging=deps["setup_cli_logging"],
            generate_report=deps["generate_report"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "verify":
        return deps["handle_verify_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            verify_hits=deps["verify_hits"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "recover-notes":
        return deps["handle_recover_notes_command"](
            args,
            resolve_path=deps["resolve_path"],
            timestamp_now=deps["timestamp_now"],
            build_timestamped_dir=deps["build_timestamped_dir"],
            setup_cli_logging=deps["setup_cli_logging"],
            recover_notes_by_keyword=deps["recover_notes_by_keyword"],
            generate_text_bundle=deps["generate_text_bundle"],
            run_pipeline=deps["run_pipeline"],
            finalize_pipeline=deps["finalize_pipeline"],
            assert_pipeline_ok=deps["assert_pipeline_ok"],
        )
    if args.command == "wizard":
        return deps["handle_wizard_command"](
            args,
            timestamp_now=deps["timestamp_now"],
            setup_cli_logging=deps["setup_cli_logging"],
            run_wizard=deps["run_wizard"],
        )
    if args.command == "gui":
        return deps["handle_gui_command"](run_gui=deps["run_gui"])
    return None
