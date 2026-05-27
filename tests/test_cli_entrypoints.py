import argparse
import subprocess
import sys

from notes_recovery.cli.main import main
from notes_recovery.cli.parser import build_parser


def _get_subcommands(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices.keys())
    return set()


def test_parser_has_core_commands() -> None:
    parser = build_parser()
    commands = _get_subcommands(parser)
    expected = {
        "doctor",
        "ai-review",
        "ask-case",
        "snapshot",
        "wal-isolate",
        "wal-extract",
        "query",
        "carve-gzip",
        "recover",
        "report",
        "verify",
        "plugins",
        "plugins-validate",
        "case-diff",
        "fts-index",
        "protobuf",
        "timeline",
        "spotlight-parse",
        "recover-notes",
        "auto",
        "demo",
        "public-safe-export",
        "wizard",
        "gui",
        "flatten",
    }
    assert expected.issubset(commands)


def test_cli_help_exit() -> None:
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("--help should exit")


def test_module_execution_help_emits_usage_text() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "notes_recovery.cli.main", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "usage: notes-recovery" in completed.stdout
    assert "Start here:" in completed.stdout
    assert "notes-recovery doctor" in completed.stdout
    assert "notes-recovery ai-review --demo" in completed.stdout
    assert "notes-recovery ask-case --demo" in completed.stdout
