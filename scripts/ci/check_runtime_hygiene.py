from __future__ import annotations

import sys
from pathlib import Path

try:
    from scripts.ci.contracts import RUNTIME_HYGIENE_TOKENS
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from contracts import RUNTIME_HYGIENE_TOKENS


REQUIRED_GITIGNORE_MARKERS = (
    ".agents/",
    ".runtime-cache/",
    "cache/",
    "logs/",
    "output/",
    "examples/",
)

ALLOWED_EXAMPLE_FILES = {
    "README.md",
    ".gitkeep",
}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def collect_runtime_hygiene_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    gitignore_text = _read_text(repo_root / ".gitignore")
    if not gitignore_text:
        errors.append("missing .gitignore")
    else:
        for marker in REQUIRED_GITIGNORE_MARKERS:
            if marker not in gitignore_text:
                errors.append(f".gitignore is missing runtime-hygiene marker: {marker}")

    readme_text = _read_text(repo_root / "README.md")
    if not readme_text:
        errors.append("missing README.md")
    else:
        for token in RUNTIME_HYGIENE_TOKENS:
            if token not in readme_text:
                errors.append(f"README.md is missing runtime-hygiene contract token: {token}")

    examples_dir = repo_root / "examples"
    if examples_dir.exists():
        for path in sorted(examples_dir.iterdir()):
            if path.name in ALLOWED_EXAMPLE_FILES:
                continue
            errors.append(
                "examples/ must stay empty or contain only an approved sentinel file: "
                f"{path.name}"
            )

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors = collect_runtime_hygiene_errors(repo_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("runtime hygiene check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
