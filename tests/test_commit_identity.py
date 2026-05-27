from __future__ import annotations

import os
import subprocess
from pathlib import Path

from scripts.ci.check_commit_identity import (
    CONFIG_EMAIL_EXAMPLE,
    CONFIG_NAME_EXAMPLE,
    DEPENDABOT_NAME,
    GITHUB_EMAIL,
    GITHUB_NAME,
    LEGACY_PERSONAL_EMAILS,
    LEGACY_PERSONAL_NAME_EXAMPLES,
    LEGACY_NAME_EXAMPLE,
    collect_config_identity_errors,
    collect_history_identity_errors,
    collect_identity_errors,
)


def _git(
    repo_root: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-b", "main")
    _git(repo_root, "config", "user.name", CONFIG_NAME_EXAMPLE)
    _git(repo_root, "config", "user.email", CONFIG_EMAIL_EXAMPLE)
    return repo_root


def _commit(
    repo_root: Path,
    *,
    filename: str,
    content: str,
    message: str,
    author_name: str | None = None,
    author_email: str | None = None,
    committer_name: str | None = None,
    committer_email: str | None = None,
) -> None:
    file_path = repo_root / filename
    file_path.write_text(content, encoding="utf-8")
    _git(repo_root, "add", filename)

    env = os.environ.copy()
    if author_name is not None:
        env["GIT_AUTHOR_NAME"] = author_name
    if author_email is not None:
        env["GIT_AUTHOR_EMAIL"] = author_email
    if committer_name is not None:
        env["GIT_COMMITTER_NAME"] = committer_name
    if committer_email is not None:
        env["GIT_COMMITTER_EMAIL"] = committer_email

    _git(repo_root, "commit", "-m", message, env=env)


def test_commit_identity_allows_primary_config_and_legacy_history(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    _commit(
        repo_root,
        filename="README.md",
        content="legacy\n",
        message="legacy history",
        author_name=LEGACY_NAME_EXAMPLE,
        author_email=CONFIG_EMAIL_EXAMPLE,
        committer_name=LEGACY_NAME_EXAMPLE,
        committer_email=CONFIG_EMAIL_EXAMPLE,
    )

    assert collect_identity_errors(repo_root, mode="all") == []


def test_commit_identity_rejects_legacy_personal_identity(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    legacy_name = sorted(LEGACY_PERSONAL_NAME_EXAMPLES)[0]
    legacy_email = sorted(LEGACY_PERSONAL_EMAILS)[0]
    _commit(
        repo_root,
        filename="README.md",
        content="legacy personal\n",
        message="legacy personal identity",
        author_name=legacy_name,
        author_email=legacy_email,
        committer_name=legacy_name,
        committer_email=legacy_email,
    )

    errors = collect_history_identity_errors(repo_root)

    assert any("author" in error and legacy_name in error for error in errors)
    assert any("committer" in error and legacy_name in error for error in errors)


def test_commit_identity_rejects_wrong_repo_local_identity(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    _git(repo_root, "config", "user.name", "Codex")

    errors = collect_config_identity_errors(repo_root)

    assert any("repo-local git user.name" in error for error in errors)
    assert any("GIT_AUTHOR_IDENT" in error for error in errors)


def test_commit_identity_rejects_non_allowlisted_commit_identity(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    _commit(
        repo_root,
        filename="README.md",
        content="bot\n",
        message="bad author",
        author_name="github-actions[bot]",
        author_email="41898282+github-actions[bot]@users.noreply.github.com",
        committer_name="github-actions[bot]",
        committer_email="41898282+github-actions[bot]@users.noreply.github.com",
    )

    errors = collect_history_identity_errors(repo_root)

    assert any("author" in error and "github-actions[bot]" in error for error in errors)
    assert any("committer" in error and "github-actions[bot]" in error for error in errors)


def test_commit_identity_rejects_codex_coauthor_trailer(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    _commit(
        repo_root,
        filename="README.md",
        content="coauthor\n",
        message="normal subject\n\nCo-authored-by: Codex <codex@example.com>",
    )

    errors = collect_history_identity_errors(repo_root)

    assert any("Co-authored-by trailer" in error and "Codex" in error for error in errors)


def test_commit_identity_allows_dependabot_exception(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    _commit(
        repo_root,
        filename="README.md",
        content="dependabot\n",
        message="dependabot bump",
        author_name=DEPENDABOT_NAME,
        author_email="49699333+dependabot[bot]@users.noreply.github.com",
        committer_name=DEPENDABOT_NAME,
        committer_email="49699333+dependabot[bot]@users.noreply.github.com",
    )

    assert collect_history_identity_errors(repo_root) == []


def test_commit_identity_rejects_spoofed_dependabot_noreply_email(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    _commit(
        repo_root,
        filename="README.md",
        content="spoofed\n",
        message="spoofed dependabot",
        author_name=DEPENDABOT_NAME,
        author_email="99999999+dependabot[bot]@users.noreply.github.com",
        committer_name=DEPENDABOT_NAME,
        committer_email="99999999+dependabot[bot]@users.noreply.github.com",
    )

    errors = collect_history_identity_errors(repo_root)

    assert any("author" in error and DEPENDABOT_NAME in error for error in errors)


def test_commit_identity_ignores_github_synthetic_merge_commit(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    _commit(
        repo_root,
        filename="README.md",
        content="main\n",
        message="main base",
    )
    _git(repo_root, "switch", "-c", "feature")
    _commit(
        repo_root,
        filename="feature.txt",
        content="feature\n",
        message="feature commit",
    )
    _git(repo_root, "switch", "main")

    env = os.environ.copy()
    env["GIT_COMMITTER_NAME"] = GITHUB_NAME
    env["GIT_COMMITTER_EMAIL"] = GITHUB_EMAIL
    _git(
        repo_root,
        "merge",
        "--no-ff",
        "feature",
        "-m",
        "Merge feature into main",
        env=env,
    )

    assert collect_history_identity_errors(repo_root) == []


def test_commit_identity_allows_github_platform_committer_with_primary_author(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    _commit(
        repo_root,
        filename="README.md",
        content="platform\n",
        message="platform commit",
        author_name=CONFIG_NAME_EXAMPLE,
        author_email=CONFIG_EMAIL_EXAMPLE,
        committer_name=GITHUB_NAME,
        committer_email=GITHUB_EMAIL,
    )

    assert collect_history_identity_errors(repo_root) == []


def test_commit_identity_allows_github_hosted_squash_merge_commit_with_owner_noreply(tmp_path: Path) -> None:
    repo_root = _init_repo(tmp_path)
    _commit(
        repo_root,
        filename="base.txt",
        content="base\n",
        message="base commit",
    )
    _commit(
        repo_root,
        filename="README.md",
        content="squash merge\n",
        message="fix(governance): harden closeout gates (#2)",
        author_name=CONFIG_NAME_EXAMPLE,
        author_email=CONFIG_EMAIL_EXAMPLE,
        committer_name=GITHUB_NAME,
        committer_email=GITHUB_EMAIL,
    )

    assert collect_history_identity_errors(repo_root) == []


def test_commit_identity_allows_github_hosted_squash_merge_commit_with_missing_parent_metadata(
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    legacy_name = sorted(LEGACY_PERSONAL_NAME_EXAMPLES)[0]
    legacy_email = sorted(LEGACY_PERSONAL_EMAILS)[0]
    _commit(
        repo_root,
        filename="README.md",
        content="shallow squash merge\n",
        message="fix(ci): accept hosted squash merge identity (#4)",
        author_name=legacy_name,
        author_email=legacy_email,
        committer_name=GITHUB_NAME,
        committer_email=GITHUB_EMAIL,
    )

    assert collect_history_identity_errors(repo_root) == []


def test_commit_identity_allows_github_hosted_squash_merge_commit_without_pr_suffix(
    tmp_path: Path,
) -> None:
    repo_root = _init_repo(tmp_path)
    _commit(
        repo_root,
        filename="base.txt",
        content="base\n",
        message="base commit",
    )
    legacy_name = sorted(LEGACY_PERSONAL_NAME_EXAMPLES)[0]
    legacy_email = sorted(LEGACY_PERSONAL_EMAILS)[0]
    _commit(
        repo_root,
        filename="README.md",
        content="hosted squash merge without PR suffix\n",
        message="fix: tighten distribution truth and ci layering",
        author_name=legacy_name,
        author_email=legacy_email,
        committer_name=GITHUB_NAME,
        committer_email=GITHUB_EMAIL,
    )

    assert collect_history_identity_errors(repo_root) == []
