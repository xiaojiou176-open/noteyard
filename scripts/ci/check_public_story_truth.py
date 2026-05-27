from __future__ import annotations

import sys
from pathlib import Path

try:
    from scripts.ci.contracts import (
        PUBLIC_STORY_FORBIDDEN_CHANGELOG_TOKENS,
        PUBLIC_STORY_FORBIDDEN_DOC_TOKENS,
        README_TAG_RELEASE_URL,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from contracts import (
        PUBLIC_STORY_FORBIDDEN_CHANGELOG_TOKENS,
        PUBLIC_STORY_FORBIDDEN_DOC_TOKENS,
        README_TAG_RELEASE_URL,
    )

TAIL_HANDLER_TAG_RELEASE_URL = README_TAG_RELEASE_URL


def _read(repo_root: Path, rel_path: str) -> str | None:
    path = repo_root / rel_path
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _contains_overclaimed_distribution_token(text: str, token: str) -> bool:
    for line in text.splitlines():
        if token not in line:
            continue
        if "without fresh PyPI read-back" in line:
            continue
        return True
    return False


def collect_public_story_truth_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    readme_text = _read(repo_root, "README.md")
    if readme_text is None:
        return ["missing README.md"]

    changelog_text = _read(repo_root, "CHANGELOG.md")
    if changelog_text is None:
        return ["missing CHANGELOG.md"]

    tail_handler_text = _read(repo_root, "notes_recovery/cli/tail_handlers.py")
    if tail_handler_text is None:
        return ["missing notes_recovery/cli/tail_handlers.py"]

    if README_TAG_RELEASE_URL in readme_text:
        errors.append("README.md must not link to a tag-specific release URL until a real release exists")
    if TAIL_HANDLER_TAG_RELEASE_URL in tail_handler_text:
        errors.append("tail_handlers.py must not advertise a tag-specific release URL until a real release exists")

    for token in PUBLIC_STORY_FORBIDDEN_CHANGELOG_TOKENS:
        if token in changelog_text:
            errors.append(f"CHANGELOG.md contains a stale public-story claim: {token}")

    for rel_path in ("README.md", "DISTRIBUTION.md", "INTEGRATIONS.md"):
        text = _read(repo_root, rel_path)
        if text is None:
            continue
        for token in PUBLIC_STORY_FORBIDDEN_DOC_TOKENS:
            if _contains_overclaimed_distribution_token(text, token):
                errors.append(f"{rel_path} contains an over-claimed distribution token: {token}")

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors = collect_public_story_truth_errors(repo_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("public story truth check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
