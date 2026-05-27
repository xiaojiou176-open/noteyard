from __future__ import annotations

from pathlib import Path

from scripts.ci.check_host_safety_contract import collect_host_safety_contract_errors
from scripts.ci.contracts import (
    HOST_SAFETY_CHECK_TOKEN,
    HOST_SAFETY_DOC_TOKENS_BY_FILE,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_minimal_host_safety_surface(tmp_path: Path) -> None:
    for relative_path, tokens in HOST_SAFETY_DOC_TOKENS_BY_FILE.items():
        _write(tmp_path / relative_path, "# Doc\n" + "\n".join(tokens) + "\n")

    _write(
        tmp_path / ".pre-commit-config.yaml",
        f"repos:\n  - repo: local\n    hooks:\n      - id: host-safety\n        entry: python3 scripts/ci/{HOST_SAFETY_CHECK_TOKEN}\n",
    )
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        f"name: CI\njobs:\n  repo-hygiene:\n    steps:\n      - run: python scripts/ci/{HOST_SAFETY_CHECK_TOKEN}\n",
    )


def test_host_safety_contract_passes_for_minimal_safe_repo(tmp_path: Path) -> None:
    _write_minimal_host_safety_surface(tmp_path)
    _write(tmp_path / "notes_recovery" / "services" / "safe.py", "def safe() -> str:\n    return 'ok'\n")
    _write(
        tmp_path / "tests" / "test_safe.py",
        "def test_safe() -> None:\n    assert True\n",
    )

    assert collect_host_safety_contract_errors(tmp_path) == []


def test_host_safety_contract_detects_missing_doc_token(tmp_path: Path) -> None:
    _write_minimal_host_safety_surface(tmp_path)
    _write(tmp_path / "AGENTS.md", "# Agent Navigation\ncopied evidence only\n")

    errors = collect_host_safety_contract_errors(tmp_path)

    assert any("AGENTS.md is missing host-safety token" in error for error in errors)


def test_host_safety_contract_detects_forbidden_runtime_primitive(tmp_path: Path) -> None:
    _write_minimal_host_safety_surface(tmp_path)
    _write(
        tmp_path / "notes_recovery" / "services" / "bad.py",
        "import os\n\n\ndef bad() -> None:\n    os.kill(123, 9)\n",
    )

    errors = collect_host_safety_contract_errors(tmp_path)

    assert any("forbidden host-control primitive: os.kill(...)" in error for error in errors)


def test_host_safety_contract_fails_closed_on_syntax_error(tmp_path: Path) -> None:
    _write_minimal_host_safety_surface(tmp_path)
    _write(
        tmp_path / "notes_recovery" / "services" / "broken.py",
        "def broken(:\n    pass\n",
    )

    errors = collect_host_safety_contract_errors(tmp_path)

    assert any("could not be parsed for host-safety scanning" in error for error in errors)


def test_host_safety_contract_detects_case_insensitive_tokens_and_os_system(tmp_path: Path) -> None:
    _write_minimal_host_safety_surface(tmp_path)
    _write(
        tmp_path / "notes_recovery" / "services" / "bad.py",
        "import os\n\n\ndef bad() -> None:\n    os.system('KiLlAlL Finder')\n",
    )

    errors = collect_host_safety_contract_errors(tmp_path)

    assert any("forbidden host-control primitive: killall" in error for error in errors)


def test_host_safety_contract_allows_warning_text_in_docs(tmp_path: Path) -> None:
    _write_minimal_host_safety_surface(tmp_path)
    _write(
        tmp_path / "README.md",
        "# Noteyard\nHost Safety Boundary\ncopied-evidence workbench\nAvoid killall, pkill, osascript, AppleEvent, and loginwindow flows.\n",
    )
    _write(tmp_path / "notes_recovery" / "services" / "safe.py", "def safe() -> str:\n    return 'ok'\n")

    assert collect_host_safety_contract_errors(tmp_path) == []
