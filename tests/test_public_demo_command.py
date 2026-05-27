from __future__ import annotations

from types import SimpleNamespace

from notes_recovery.cli.tail_handlers import handle_demo_command


def test_demo_command_prints_public_surface(tmp_path, capsys) -> None:
    demo_dir = tmp_path / "notes_recovery" / "resources" / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    (demo_dir / "sanitized-case-tree.txt").write_text(
        "Notes_Forensics_2026-03-25/\n  DB_Backup/\n  Verification_2026-03-25/\n",
        encoding="utf-8",
    )
    (demo_dir / "sanitized-verification-summary.txt").write_text(
        "Verification summary\nMatched keyword: orchard lane\nTop hit count: 3\n",
        encoding="utf-8",
    )
    (demo_dir / "sanitized-operator-brief.md").write_text(
        "# Operator brief\n- Recovery stayed copy-first\n- Review artifacts were written\n",
        encoding="utf-8",
    )
    (demo_dir / "sanitized-ai-triage-summary.md").write_text(
        "# AI Triage Summary\n- Synthetic AI proof\n",
        encoding="utf-8",
    )

    exit_code = handle_demo_command(
        SimpleNamespace(),
        timestamp_now=lambda: "2026-03-25T12-00-00Z",
        setup_cli_logging=lambda *_args, **_kwargs: None,
        repo_root=tmp_path,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Noteyard public demo" in captured.out
    assert "sanitized-case-tree.txt" in captured.out
    assert "Verification summary" in captured.out
    assert "AI triage preview" in captured.out
    assert "notes-recovery ai-review --demo" in captured.out
    assert "Changelog:" in captured.out
    assert "README.md in the repository root" in captured.out
    assert "notes-recovery doctor" in captured.out
    assert "notes-recovery --help" in captured.out


def test_demo_command_does_not_default_logs_into_repo_root(tmp_path) -> None:
    demo_dir = tmp_path / "notes_recovery" / "resources" / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    (demo_dir / "sanitized-case-tree.txt").write_text("case-tree\n", encoding="utf-8")
    (demo_dir / "sanitized-verification-summary.txt").write_text("verification\n", encoding="utf-8")
    (demo_dir / "sanitized-operator-brief.md").write_text("operator brief\n", encoding="utf-8")
    (demo_dir / "sanitized-ai-triage-summary.md").write_text("ai triage\n", encoding="utf-8")

    calls: list[tuple[object, str, object, str]] = []

    def fake_setup_cli_logging(args, run_ts, auto_dir, command) -> None:
        calls.append((args, run_ts, auto_dir, command))

    exit_code = handle_demo_command(
        SimpleNamespace(),
        timestamp_now=lambda: "2026-03-25T12-30-00Z",
        setup_cli_logging=fake_setup_cli_logging,
        repo_root=tmp_path,
    )

    assert exit_code == 0
    assert calls == [(calls[0][0], "2026-03-25T12-30-00Z", None, "demo")]
