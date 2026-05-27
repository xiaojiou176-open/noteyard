from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    from scripts.ci.contracts import ROOT_PUBLIC_CONTRACT_FILES, README_PUBLIC_SURFACE_TOKENS
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from contracts import ROOT_PUBLIC_CONTRACT_FILES, README_PUBLIC_SURFACE_TOKENS

FORBIDDEN_LOCAL_README_PREFIXES = (
    "./docs/",
    "docs/",
)

LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def collect_docs_surface_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    for rel_path in ROOT_PUBLIC_CONTRACT_FILES:
        if not (repo_root / rel_path).exists():
            errors.append(f"missing required docs surface file: {rel_path}")

    readme_path = repo_root / "README.md"
    if not readme_path.exists():
        return errors

    readme_text = readme_path.read_text(encoding="utf-8")

    for token in README_PUBLIC_SURFACE_TOKENS:
        if token not in readme_text:
            errors.append(f"README.md is missing required surface token: {token}")

    for match in LINK_PATTERN.finditer(readme_text):
        target = match.group(1).strip()
        if not target or "://" in target or target.startswith("#"):
            continue
        if target.startswith("mailto:"):
            continue
        if target.startswith(FORBIDDEN_LOCAL_README_PREFIXES):
            errors.append(f"README.md must not link to the removed docs surface: {target}")
            continue
        normalized = target.split("#", 1)[0]
        if not normalized:
            continue
        if not (repo_root / normalized).exists():
            errors.append(f"README.md contains a broken local link: {target}")

    if (repo_root / "docs").exists():
        errors.append("docs/ must not exist in the minimal public surface")

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors = collect_docs_surface_errors(repo_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("docs surface check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
