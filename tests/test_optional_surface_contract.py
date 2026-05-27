from __future__ import annotations

from pathlib import Path

from scripts.ci.check_optional_surface_contract import collect_optional_surface_contract_errors


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_optional_surface_contract_passes_for_aligned_docs(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "pip install -e .[ai]",
                "pip install -e .[mcp]",
                "pip install -e .[dashboard]",
                "pip install -e .[carve]",
                "`.[ai]`",
                "`.[mcp]`",
                "`dashboard`",
                "`carve`",
                "notes-recovery-mcp",
            ]
        ),
    )
    _write(
        tmp_path / "CONTRIBUTING.md",
        "\n".join(
            [
                "tests/test_ai_review.py",
                "tests/test_ask_case.py",
                "tests/test_mcp_server.py",
                "tests/test_dashboard_full.py",
                "tests/test_carve.py",
                "different transitive dependency sets",
                "one mixed environment",
                "stdio",
                "read-only / read-mostly",
                "case-root-centric",
                "ollama",
                "docker",
                "sqlite_dissect",
                "strings",
                "binwalk",
                "not part of the default baseline guarantee",
                "opt-in integrations",
            ]
        ),
    )

    assert collect_optional_surface_contract_errors(tmp_path) == []


def test_optional_surface_contract_detects_missing_contributing_tokens(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "`.[ai]`\n`.[mcp]`\n`dashboard`\n`carve`\npip install -e .[ai]\npip install -e .[mcp]\npip install -e .[dashboard]\nnotes-recovery-mcp\n")
    _write(tmp_path / "CONTRIBUTING.md", "tests/test_dashboard_full.py\ndifferent transitive dependency sets\n")

    errors = collect_optional_surface_contract_errors(tmp_path)
    assert any("CONTRIBUTING.md is missing optional-surface token" in error for error in errors)
