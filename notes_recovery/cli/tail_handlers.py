from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from notes_recovery.case_contract import CASE_DIR_AI_REVIEW
from notes_recovery.case_contract import CASE_DIR_VERIFICATION, prefixed_case_dir
from notes_recovery.models import ExitCode, PipelineStage
from notes_recovery.services.ask_case import render_ask_case_result


def _read_excerpt(path: Path, *, max_lines: int) -> list[str]:
    if not path.exists():
        return [f"(missing: {path.name})"]

    lines = path.read_text(encoding="utf-8").splitlines()
    excerpt = [line.rstrip() for line in lines[:max_lines] if line.strip()]
    return excerpt or [f"(empty: {path.name})"]


def _demo_resource_path(repo_root: Path, name: str) -> Path:
    return repo_root / "notes_recovery" / "resources" / "demo" / name


def handle_demo_command(
    args,
    *,
    timestamp_now: Callable[[], str],
    setup_cli_logging: Callable[..., Any],
    repo_root: Path,
) -> int:
    run_ts = timestamp_now()
    setup_cli_logging(args, run_ts, None, "demo")

    repo_url = "https://github.com/xiaojiou176-open/notes-recover"
    release_url = "https://github.com/xiaojiou176-open/notes-recover/releases"
    changelog_url = "https://github.com/xiaojiou176-open/notes-recover/blob/main/CHANGELOG.md"
    support_url = "https://github.com/xiaojiou176-open/notes-recover/blob/main/SUPPORT.md"
    case_tree_path = _demo_resource_path(repo_root, "sanitized-case-tree.txt")
    verify_path = _demo_resource_path(repo_root, "sanitized-verification-summary.txt")
    operator_path = _demo_resource_path(repo_root, "sanitized-operator-brief.md")
    ai_triage_path = _demo_resource_path(repo_root, "sanitized-ai-triage-summary.md")
    required_paths = (case_tree_path, verify_path, operator_path)

    missing = [path for path in required_paths if not path.exists()]
    if missing:
        print("NotesRecover public demo is unavailable because tracked demo artifacts are missing:")
        for path in missing:
            print(f"- {path}")
        return ExitCode.ERROR.value

    print("NotesRecover public demo")
    print("")
    print("Zero-risk first look for the copy-first Apple Notes recovery workflow.")
    print("Nothing in this command touches private evidence or a live Notes store.")
    print("")
    print("Live entrypoints")
    print(f"- Repository: {repo_url}")
    print(f"- Releases: {release_url}")
    print(f"- Changelog: {changelog_url}")
    print(f"- Support: {support_url}")
    print("")
    print("Local demo artifacts")
    print(f"- Case tree: {case_tree_path.relative_to(repo_root)}")
    print(f"- Verification summary: {verify_path.relative_to(repo_root)}")
    print(f"- Operator brief: {operator_path.relative_to(repo_root)}")
    if ai_triage_path.exists():
        print(f"- AI triage summary: {ai_triage_path.relative_to(repo_root)}")
    print("")
    print("Case tree preview")
    for line in _read_excerpt(case_tree_path, max_lines=6):
        print(f"  {line}")
    print("")
    print("Verification preview")
    for line in _read_excerpt(verify_path, max_lines=5):
        print(f"  {line}")
    print("")
    print("Operator brief preview")
    for line in _read_excerpt(operator_path, max_lines=5):
        print(f"  {line}")
    print("")
    if ai_triage_path.exists():
        print("AI triage preview")
        for line in _read_excerpt(ai_triage_path, max_lines=6):
            print(f"  {line}")
        print("")
    print("Next steps")
    print("- Read README.md in the repository root for the public contract.")
    print("- Run `notes-recovery doctor` before the first real copied-evidence run.")
    print("- Run `notes-recovery ai-review --demo` for a synthetic AI-assisted review proof.")
    print("- Inspect the local demo files under notes_recovery/resources/demo/.")
    print("- Run `notes-recovery --help` when you want the full command map.")
    return ExitCode.OK.value


def handle_doctor_command(
    args,
    *,
    timestamp_now: Callable[[], str],
    setup_cli_logging: Callable[..., Any],
    run_doctor: Callable[[], dict[str, Any]],
) -> int:
    run_ts = timestamp_now()
    if not getattr(args, "json", False):
        setup_cli_logging(args, run_ts, None, "doctor")
    payload = run_doctor()
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        from notes_recovery.services.doctor import render_doctor_report

        print(render_doctor_report(payload), end="")
    if payload.get("overall_status") == "fix-first":
        return ExitCode.ERROR.value
    return ExitCode.OK.value


def handle_ai_review_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    run_ai_review: Callable[..., dict[str, str]],
) -> int:
    run_ts = timestamp_now()
    setup_cli_logging(args, run_ts, None, "ai-review")

    demo = bool(getattr(args, "demo", False))
    root_dir = resolve_path(args.dir) if getattr(args, "dir", None) else None
    if demo and root_dir is not None:
        raise RuntimeError("Use either `--demo` or `--dir`, not both.")
    if not demo and root_dir is None:
        raise RuntimeError("`notes-recovery ai-review` requires either `--dir <case-root>` or `--demo`.")

    if getattr(args, "out", None):
        out_dir = build_timestamped_dir(resolve_path(args.out), run_ts)
    elif demo:
        out_dir = build_timestamped_dir(resolve_path("./output/AI_Review_Demo"), run_ts)
    else:
        out_dir = prefixed_case_dir(root_dir, CASE_DIR_AI_REVIEW, run_ts)

    outputs = run_ai_review(
        root_dir=root_dir,
        out_dir=out_dir,
        run_ts=run_ts,
        demo=demo,
        provider=getattr(args, "provider", None),
        model=getattr(args, "model", None),
        ollama_base_url=getattr(args, "ollama_base_url", None),
        openai_api_key=getattr(args, "openai_api_key", None),
        allow_cloud=getattr(args, "allow_cloud", False),
        timeout_sec=getattr(args, "timeout_sec", 120),
        repo_root=Path(__file__).resolve().parents[2],
    )
    print(f"AI review outputs written: {out_dir}")
    print(f"Triage summary: {outputs['triage_summary']}")
    print(f"Top findings: {outputs['top_findings']}")
    print(f"Next questions: {outputs['next_questions']}")
    print(f"Artifact priority: {outputs['artifact_priority']}")
    return ExitCode.OK.value


def handle_ask_case_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    setup_cli_logging: Callable[..., Any],
    run_ask_case: Callable[..., dict[str, Any]],
) -> int:
    run_ts = timestamp_now()
    demo = bool(getattr(args, "demo", False))
    root_dir = resolve_path(args.dir) if getattr(args, "dir", None) else None
    if demo and root_dir is not None:
        raise RuntimeError("Use either `--demo` or `--dir`, not both.")
    if not demo and root_dir is None:
        raise RuntimeError("`notes-recovery ask-case` requires either `--dir <case-root>` or `--demo`.")
    setup_cli_logging(args, run_ts, root_dir, "ask-case")
    payload = run_ask_case(
        root_dir=root_dir,
        question=args.question,
        demo=demo,
        repo_root=Path(__file__).resolve().parents[2],
        provider=getattr(args, "provider", None),
        model=getattr(args, "model", None),
        ollama_base_url=getattr(args, "ollama_base_url", None),
        openai_api_key=getattr(args, "openai_api_key", None),
        allow_cloud=getattr(args, "allow_cloud", False),
        timeout_sec=getattr(args, "timeout_sec", 120),
    )
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print(render_ask_case_result(payload), end="")
    return ExitCode.OK.value


def handle_plugins_validate_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    setup_cli_logging: Callable[..., Any],
    validate_plugins_config: Callable[..., dict[str, Any]],
    render_plugins_validation_report: Callable[[dict[str, Any]], str],
) -> int:
    run_ts = timestamp_now()
    root_dir = resolve_path(args.dir) if getattr(args, "dir", None) else None
    db_path = resolve_path(args.db) if getattr(args, "db", None) else None
    setup_cli_logging(args, run_ts, root_dir, "plugins-validate")
    payload = validate_plugins_config(
        resolve_path(args.config),
        root_dir=root_dir,
        db_path=db_path,
    )
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print(render_plugins_validation_report(payload), end="")
    if payload.get("overall_status") == "fail":
        return ExitCode.ERROR.value
    return ExitCode.OK.value


def handle_case_diff_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    build_case_diff_payload: Callable[[Path, Path], dict[str, Any]],
    write_case_diff_outputs: Callable[[Path, dict[str, Any]], dict[str, str]],
) -> int:
    run_ts = timestamp_now()
    case_a = resolve_path(args.dir_a)
    case_b = resolve_path(args.dir_b)
    out_dir = (
        build_timestamped_dir(resolve_path(args.out), run_ts)
        if getattr(args, "out", None)
        else build_timestamped_dir(Path("./output/Case_Diff"), run_ts)
    )
    setup_cli_logging(args, run_ts, out_dir, "case-diff")
    payload = build_case_diff_payload(case_a, case_b)
    outputs = write_case_diff_outputs(out_dir, payload)
    print(f"Case diff outputs written: {out_dir}")
    print(f"Summary: {outputs['summary']}")
    print(f"JSON: {outputs['json']}")
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    return ExitCode.OK.value


def handle_public_safe_export_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    public_safe_export: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    source_root = resolve_path(args.dir)
    run_ts = timestamp_now()
    out_dir = build_timestamped_dir(resolve_path(args.out), run_ts)
    setup_cli_logging(args, run_ts, None, "public-safe-export")

    def stage_export() -> dict[str, Any]:
        outputs = public_safe_export(source_root, out_dir, run_ts)
        print(f"Public-safe export written: {out_dir}")
        return outputs

    stages = [
        PipelineStage("public-safe-export", True, True, stage_export),
    ]
    stage_results = run_pipeline(stages)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_report_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_file: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    generate_report: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    root_dir = resolve_path(args.dir)
    run_ts = timestamp_now()
    if args.out:
        out_path = build_timestamped_file(resolve_path(args.out), run_ts)
    else:
        out_path = root_dir / f"report_{run_ts}.html"
    setup_cli_logging(args, run_ts, root_dir, "report")

    def stage_report() -> dict[str, Any]:
        generate_report(root_dir, args.keyword, out_path, args.max_items)
        print(f"Report generated: {out_path}")
        return {"report_path": str(out_path)}

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(root_dir, run_ts, args.keyword))}

    stages = [
        PipelineStage("report", True, True, stage_report),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "root_dir": str(root_dir),
        "keyword": args.keyword,
        "out_path": str(out_path),
        "max_items": args.max_items,
    }
    finalize_pipeline(root_dir, run_ts, "report", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_verify_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    verify_hits: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    root_dir = resolve_path(args.dir)
    run_ts = timestamp_now()
    if args.out:
        out_dir = build_timestamped_dir(resolve_path(args.out), run_ts)
    else:
        out_dir = prefixed_case_dir(root_dir, CASE_DIR_VERIFICATION, run_ts)
    setup_cli_logging(args, run_ts, out_dir, "verify")

    def stage_verify() -> dict[str, Any]:
        verify_hits(
            root_dir,
            args.keyword,
            args.top,
            args.preview_len,
            out_dir,
            deep=not args.no_deep,
            deep_max_mb=args.deep_max_mb,
            deep_max_hits_per_file=args.deep_max_hits_per_file,
            match_all=args.match_all,
            fuzzy=not args.no_fuzzy,
            fuzzy_threshold=args.fuzzy_threshold,
            fuzzy_boost=args.fuzzy_boost,
            fuzzy_max_len=args.fuzzy_max_len,
            run_ts=run_ts,
            deep_all=not args.deep_core_only,
        )
        return {"verify_dir": str(out_dir)}

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(out_dir, run_ts, args.keyword))}

    stages = [
        PipelineStage("verify", True, True, stage_verify),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "root_dir": str(root_dir),
        "keyword": args.keyword,
        "out_dir": str(out_dir),
        "top": args.top,
        "preview_len": args.preview_len,
        "deep": not args.no_deep,
        "deep_max_mb": args.deep_max_mb,
        "deep_max_hits_per_file": args.deep_max_hits_per_file,
        "deep_all": not args.deep_core_only,
        "match_all": args.match_all,
        "fuzzy": not args.no_fuzzy,
        "fuzzy_threshold": args.fuzzy_threshold,
        "fuzzy_boost": args.fuzzy_boost,
        "fuzzy_max_len": args.fuzzy_max_len,
    }
    finalize_pipeline(out_dir, run_ts, "verify", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_recover_notes_command(
    args,
    *,
    resolve_path: Callable[[str], Path],
    timestamp_now: Callable[[], str],
    build_timestamped_dir: Callable[[Path, str], Path],
    setup_cli_logging: Callable[..., Any],
    recover_notes_by_keyword: Callable[..., Any],
    generate_text_bundle: Callable[..., Any],
    run_pipeline: Callable[[list[PipelineStage]], list[Any]],
    finalize_pipeline: Callable[..., Any],
    assert_pipeline_ok: Callable[[list[Any]], None],
) -> int:
    root_dir = resolve_path(args.dir)
    run_ts = timestamp_now()
    base_out = resolve_path(args.out) if args.out else (root_dir / "Recovered_Notes")
    out_dir = build_timestamped_dir(base_out, run_ts)
    setup_cli_logging(args, run_ts, out_dir, "recover-notes")
    print(f"Timestamped output directory: {out_dir}")

    def stage_recover_notes() -> dict[str, Any]:
        recover_notes_by_keyword(
            root_dir,
            args.keyword,
            out_dir,
            args.min_overlap,
            args.max_fragments,
            args.max_stitch_rounds,
            not args.no_deep,
            not args.no_deep_all,
            args.deep_max_mb,
            args.deep_max_hits_per_file,
            args.match_all,
            not args.no_binary_copy,
            args.binary_copy_max_mb,
            run_ts,
        )
        return {"recover_dir": str(out_dir)}

    def stage_bundle() -> dict[str, Any]:
        return {"bundle_root": str(generate_text_bundle(out_dir, run_ts, args.keyword))}

    stages = [
        PipelineStage("recover-notes", True, True, stage_recover_notes),
        PipelineStage("text-bundle", True, True, stage_bundle),
    ]
    stage_results = run_pipeline(stages)
    config = {
        "root_dir": str(root_dir),
        "keyword": args.keyword,
        "out_dir": str(out_dir),
        "min_overlap": args.min_overlap,
        "max_fragments": args.max_fragments,
        "max_stitch_rounds": args.max_stitch_rounds,
        "deep": not args.no_deep,
        "deep_all": not args.no_deep_all,
        "deep_max_mb": args.deep_max_mb,
        "deep_max_hits_per_file": args.deep_max_hits_per_file,
        "match_all": args.match_all,
        "binary_copy": not args.no_binary_copy,
        "binary_copy_max_mb": args.binary_copy_max_mb,
    }
    finalize_pipeline(out_dir, run_ts, "recover-notes", config, stage_results)
    assert_pipeline_ok(stage_results)
    return ExitCode.OK.value


def handle_wizard_command(
    args,
    *,
    timestamp_now: Callable[[], str],
    setup_cli_logging: Callable[..., Any],
    run_wizard: Callable[[], None],
) -> int:
    run_ts = timestamp_now()
    setup_cli_logging(args, run_ts, Path.cwd(), "wizard")
    run_wizard()
    return ExitCode.OK.value


def handle_gui_command(
    *,
    run_gui: Callable[[], None],
) -> int:
    run_gui()
    return ExitCode.OK.value
