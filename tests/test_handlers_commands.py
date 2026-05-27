from pathlib import Path
from types import SimpleNamespace

import notes_recovery.cli.handlers as handlers


def _dummy_db(tmp_path: Path) -> Path:
    db = tmp_path / "NoteStore.sqlite"
    source = Path(__file__).parent / "data" / "icloud_min.sqlite"
    db.write_bytes(source.read_bytes())
    return db


def _stub_generate_text_bundle(out_dir: Path, *_args, **_kwargs) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir = out_dir / "Text_Bundle"
    bundle_dir.mkdir(exist_ok=True)
    return bundle_dir


def _stub_snapshot(out_dir: Path, *_args, **_kwargs) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "DB_Backup").mkdir(exist_ok=True)


def _stub_generate_report(root_dir: Path, _keyword, out_path: Path, _max_items: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("report", encoding="utf-8")


def test_run_command_all_branches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(handlers, "setup_cli_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handlers, "generate_text_bundle", _stub_generate_text_bundle)
    monkeypatch.setattr(handlers, "snapshot", _stub_snapshot)
    monkeypatch.setattr(
        handlers,
        "run_doctor",
        lambda: {
            "overall_status": "ready",
            "supported_boundary": {
                "host_os": "macOS only",
                "workflow_style": "copy-first local recovery and review",
                "live_store_rule": "do not operate on the original live Notes store",
            },
            "checks": [],
            "optional_extras": {},
            "optional_integrations": {},
            "recommended_next_step": "Run demo first.",
        },
    )
    monkeypatch.setattr(
        handlers,
        "run_ai_review",
        lambda **_kwargs: {
            "triage_summary": str(tmp_path / "triage_summary.md"),
            "top_findings": str(tmp_path / "top_findings.md"),
            "next_questions": str(tmp_path / "next_questions.md"),
            "artifact_priority": str(tmp_path / "artifact_priority.json"),
        },
    )
    monkeypatch.setattr(
        handlers,
        "run_ask_case",
        lambda **_kwargs: {
            "question": "What should I inspect first?",
            "answer": "Start with verification.",
            "confidence": "medium",
            "uncertainty": "",
            "evidence_refs": [],
            "suggested_next_targets": [],
        },
    )
    monkeypatch.setattr(
        handlers,
        "validate_plugins_config",
        lambda *_args, **_kwargs: {
            "contract_version": "2026-04-01.v1",
            "overall_status": "ready",
            "summary": {"ok": 1, "warn": 0, "fail": 0},
            "tools": [],
            "recommended_next_step": "Looks good.",
        },
    )
    monkeypatch.setattr(
        handlers,
        "render_plugins_validation_report",
        lambda payload: f"Plugin contract validation\n\nOverall status: {payload['overall_status']}\n",
    )
    monkeypatch.setattr(
        handlers,
        "build_case_diff_payload",
        lambda *_args, **_kwargs: {
            "diff_version": "2026-04-01.v1",
            "case_a": {"case_root_name": "A"},
            "case_b": {"case_root_name": "B"},
            "resource_presence": {"only_in_a": [], "only_in_b": [], "changed": [], "unchanged": []},
            "recommended_next_step": "Compare changed resources first.",
        },
    )
    monkeypatch.setattr(
        handlers,
        "write_case_diff_outputs",
        lambda out_dir, _payload: {
            "summary": str(out_dir / "case_diff_summary.md"),
            "json": str(out_dir / "case_diff.json"),
        },
    )
    monkeypatch.setattr(handlers, "wal_isolate", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handlers, "wal_extract", lambda *_args, **_kwargs: tmp_path / "wal_manifest.csv")
    monkeypatch.setattr(handlers, "wal_diff", lambda *_args, **_kwargs: tmp_path / "wal_diff.json")
    monkeypatch.setattr(handlers, "build_fts_index", lambda *_args, **_kwargs: tmp_path / "fts.sqlite")
    monkeypatch.setattr(handlers, "query_notes", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handlers, "parse_notes_protobuf", lambda *_args, **_kwargs: tmp_path / "protobuf.csv")
    monkeypatch.setattr(handlers, "build_timeline", lambda *_args, **_kwargs: {"timeline": "ok"})
    monkeypatch.setattr(handlers, "parse_spotlight_deep", lambda *_args, **_kwargs: {"spotlight": "ok"})
    monkeypatch.setattr(handlers, "carve_gzip", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handlers, "sqlite_recover", lambda *_args, **_kwargs: tmp_path / "NoteStore_recovered.sqlite")
    monkeypatch.setattr(handlers, "run_plugins", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handlers, "flatten_backup", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handlers, "freelist_carve", lambda *_args, **_kwargs: tmp_path / "freelist.json")
    monkeypatch.setattr(handlers, "correlate_fsevents_with_spotlight", lambda *_args, **_kwargs: {"fsevents": "ok"})
    monkeypatch.setattr(handlers, "auto_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handlers, "generate_report", _stub_generate_report)
    monkeypatch.setattr(handlers, "verify_hits", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handlers, "recover_notes_by_keyword", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handlers, "run_wizard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(handlers, "run_gui", lambda *_args, **_kwargs: None)

    db_path = _dummy_db(tmp_path)
    wal_path = tmp_path / "NoteStore.sqlite-wal"
    wal_path.write_bytes(b"wal")

    cases = [
        SimpleNamespace(command="ai-review", dir=str(tmp_path), demo=False, provider="ollama", model="llama3.1:8b", out=str(tmp_path / "ai_review"), ollama_base_url=None, timeout_sec=30),
        SimpleNamespace(command="ask-case", dir=str(tmp_path), demo=False, question="What should I inspect first?", provider="ollama", model="llama3.1:8b", ollama_base_url=None, openai_api_key=None, allow_cloud=False, timeout_sec=30, json=False),
        SimpleNamespace(command="doctor", json=False),
        SimpleNamespace(command="plugins-validate", dir=str(tmp_path), db=str(db_path), config=str(tmp_path / "plugins.json"), json=False),
        SimpleNamespace(command="case-diff", dir_a=str(tmp_path), dir_b=str(tmp_path), out=str(tmp_path / "case_diff"), json=False),
        SimpleNamespace(command="snapshot", out=str(tmp_path / "out"), include_core_spotlight=True, include_notes_cache=True),
        SimpleNamespace(command="wal-isolate", action="isolate", dir=str(tmp_path), isolate_dir="WAL_Isolation", allow_original=True),
        SimpleNamespace(
            command="wal-extract",
            dir=str(tmp_path),
            out=str(tmp_path / "wal_out"),
            wal=str(wal_path),
            keyword="Alpha",
            max_frames=10,
            page_size=0,
            dump_pages=False,
            dump_only_duplicates=False,
            strings=False,
            strings_min_len=4,
            strings_max_chars=200,
        ),
        SimpleNamespace(
            command="wal-diff",
            wal_a=str(wal_path),
            wal_b=str(wal_path),
            out=str(tmp_path / "wal_diff"),
            page_size=0,
            max_frames=10,
        ),
        SimpleNamespace(
            command="fts-index",
            dir=str(tmp_path),
            out=str(tmp_path / "fts_out"),
            keyword="Alpha",
            source="notes",
            db=None,
            db_table=None,
            db_columns=None,
            db_title_column=None,
            max_docs=10,
            max_file_mb=1,
            max_text_chars=500,
        ),
        SimpleNamespace(
            command="freelist-carve",
            db=str(db_path),
            out=str(tmp_path / "freelist_out"),
            keyword="Alpha",
            min_text_len=8,
            max_pages=10,
            max_output_mb=1,
            strings_max_chars=200,
        ),
        SimpleNamespace(command="query", db=str(db_path), keyword="Title", out=str(tmp_path / "query_out")),
        SimpleNamespace(command="protobuf", db=str(db_path), keyword=None, out=str(tmp_path / "proto_out"), max_notes=5, max_zdata_mb=1),
        SimpleNamespace(
            command="timeline",
            dir=str(tmp_path),
            keyword=None,
            out=str(tmp_path / "timeline_out"),
            max_notes=10,
            max_events=10,
            spotlight_max_files=5,
            no_fs=False,
            no_plotly=True,
        ),
        SimpleNamespace(
            command="spotlight-parse",
            dir=str(tmp_path),
            out=str(tmp_path / "spot_out"),
            max_files=5,
            max_bytes=1024,
            min_string_len=3,
            max_string_chars=200,
            max_rows_per_table=50,
        ),
        SimpleNamespace(
            command="carve-gzip",
            db=str(db_path),
            keyword=None,
            out=str(tmp_path / "carve_out"),
            max_hits=3,
            window_size=256,
            min_text_len=8,
            min_text_ratio=0.2,
            algorithms=None,
            max_output_mb=2,
        ),
        SimpleNamespace(command="recover", db=str(db_path), out=str(tmp_path / "recover_out"), ignore_freelist=False, lost_and_found="lost_and_found"),
        SimpleNamespace(command="plugins", dir=str(tmp_path), db=str(db_path), config=str(tmp_path / "plugins.json"), enable_all=False),
        SimpleNamespace(command="flatten", src=str(tmp_path), out=str(tmp_path / "flat"), no_manifest=False),
        SimpleNamespace(
            command="fsevents-correlate",
            dir=str(tmp_path),
            fsevents=str(tmp_path / "fsevents.csv"),
            spotlight_events=None,
            out=str(tmp_path / "fsevents_out"),
            window_sec=60,
            max_records=100,
        ),
        SimpleNamespace(
            command="auto",
            out=str(tmp_path / "auto"),
            keyword=None,
            skip_core_spotlight=False,
            skip_notes_cache=False,
            skip_wal=True,
            skip_query=True,
            skip_carve=True,
            recover=False,
            recover_ignore_freelist=False,
            recover_lost_and_found="lost_and_found",
            plugins=False,
            plugins_config=None,
            plugins_enable_all=False,
            report=True,
            report_out=None,
            report_max_items=10,
            carve_max_hits=3,
            carve_window_size=256,
            carve_min_text_len=8,
            carve_min_text_ratio=0.2,
            protobuf=False,
            protobuf_max_notes=5,
            protobuf_max_zdata_mb=1,
            spotlight_parse=False,
            spotlight_parse_max_files=5,
            spotlight_parse_max_bytes=1024,
            spotlight_parse_min_string_len=3,
            spotlight_parse_max_string_chars=200,
            spotlight_parse_max_rows=50,
            verify=False,
            verify_top=5,
            verify_preview_len=50,
            verify_out=None,
            verify_no_deep=True,
            verify_deep_max_mb=0,
            verify_deep_max_hits_per_file=10,
            verify_deep_core_only=True,
            verify_match_all=False,
            verify_no_fuzzy=True,
            verify_fuzzy_threshold=0.7,
            verify_fuzzy_boost=1.0,
            verify_fuzzy_max_len=200,
        ),
        SimpleNamespace(command="report", dir=str(tmp_path), out=str(tmp_path / "report.html"), keyword=None, max_items=10),
        SimpleNamespace(
            command="verify",
            dir=str(tmp_path),
            out=str(tmp_path / "verify_out"),
            keyword="Alpha",
            top=5,
            preview_len=50,
            no_deep=True,
            deep_max_mb=0,
            deep_max_hits_per_file=10,
            deep_core_only=False,
            match_all=False,
            no_fuzzy=True,
            fuzzy_threshold=0.7,
            fuzzy_boost=1.0,
            fuzzy_max_len=200,
        ),
        SimpleNamespace(
            command="recover-notes",
            dir=str(tmp_path),
            out=str(tmp_path / "recover_notes"),
            keyword="Alpha",
            min_overlap=5,
            max_fragments=10,
            max_stitch_rounds=10,
            no_deep=True,
            no_deep_all=True,
            deep_max_mb=0,
            deep_max_hits_per_file=10,
            match_all=False,
            no_binary_copy=True,
            binary_copy_max_mb=1,
        ),
        SimpleNamespace(command="wizard"),
        SimpleNamespace(command="gui"),
    ]

    for args in cases:
        code = handlers.run_command(args)
        assert code == handlers.ExitCode.OK.value


def test_plugins_validate_returns_error_for_fail_status(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(handlers, "setup_cli_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        handlers,
        "validate_plugins_config",
        lambda *_args, **_kwargs: {
            "contract_version": "2026-04-01.v1",
            "overall_status": "fail",
            "summary": {"ok": 0, "warn": 0, "fail": 1},
            "tools": [],
            "recommended_next_step": "Fix the config first.",
        },
    )
    monkeypatch.setattr(
        handlers,
        "render_plugins_validation_report",
        lambda payload: (
            "Plugin contract validation\n\n"
            f"Overall status: {payload['overall_status']}\n"
        ),
    )

    args = SimpleNamespace(
        command="plugins-validate",
        dir=str(tmp_path),
        db=str(tmp_path / "NoteStore.sqlite"),
        config=str(tmp_path / "plugins.json"),
        json=False,
        log_level="info",
        log_console_level="info",
        log_file=None,
        log_dir=None,
        log_append=False,
        log_max_bytes=0,
        log_backup_count=0,
        log_time_format="%Y-%m-%d %H:%M:%S",
        log_utc=False,
        log_json=False,
        quiet=False,
        no_log_file=True,
        case_no_manifest=False,
        case_sign="none",
        case_hmac_key=None,
        case_pgp_key=None,
        case_pgp_homedir=None,
        case_pgp_binary="gpg",
    )

    assert handlers.run_command(args) == handlers.ExitCode.ERROR.value
