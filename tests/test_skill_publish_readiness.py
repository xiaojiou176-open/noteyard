from __future__ import annotations

from pathlib import Path

from scripts.release.check_skill_publish_readiness import (
    DERIVED_SKILL_PATHS,
    LEGACY_PUBLIC_REFERENCE_FILES,
    collect_skill_publish_errors,
)


def test_collect_skill_publish_errors_passes_for_repo_root() -> None:
    errors = collect_skill_publish_errors(Path.cwd())
    assert errors == []


def test_canonical_and_derived_skill_files_match() -> None:
    repo_root = Path.cwd()
    canonical_text = (
        repo_root / "skills" / "noteyard-case-review" / "SKILL.md"
    ).read_text(encoding="utf-8")

    for rel_path in DERIVED_SKILL_PATHS:
        assert (repo_root / rel_path).read_text(encoding="utf-8") == canonical_text


def test_public_skill_packet_has_no_legacy_reference_aliases() -> None:
    repo_root = Path.cwd()
    for rel_path in LEGACY_PUBLIC_REFERENCE_FILES:
        assert not (repo_root / rel_path).exists()
