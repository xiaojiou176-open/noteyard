from __future__ import annotations

import sys
from pathlib import Path


README_TOKENS = (
    "pip install -e .[ai]",
    "pip install -e .[mcp]",
    "pip install -e .[dashboard]",
    "pip install -e .[carve]",
    "`.[ai]`",
    "`.[mcp]`",
    "`dashboard`",
    "`carve`",
    "notes-recovery-mcp",
)

CONTRIBUTING_TOKENS = (
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
)


def _read(repo_root: Path, rel_path: str) -> str:
    path = repo_root / rel_path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def collect_optional_surface_contract_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    readme_text = _read(repo_root, "README.md")
    if not readme_text:
        errors.append("missing README.md")
    else:
        for token in README_TOKENS:
            if token not in readme_text:
                errors.append(f"README.md is missing optional-surface token: {token}")

    contributing_text = _read(repo_root, "CONTRIBUTING.md")
    if not contributing_text:
        errors.append("missing CONTRIBUTING.md")
    else:
        for token in CONTRIBUTING_TOKENS:
            if token not in contributing_text:
                errors.append(f"CONTRIBUTING.md is missing optional-surface token: {token}")

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors = collect_optional_surface_contract_errors(repo_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("optional surface contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
