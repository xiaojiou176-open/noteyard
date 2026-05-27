from __future__ import annotations

import subprocess
from pathlib import Path

import scripts.ci.check_release_readiness as release_readiness
from scripts.ci.check_release_readiness import (
    _evaluate_release_summary,
    _gh_json,
    _is_meaningful_history_path_hit,
)

USERS_PREFIX = "/" + "Users" + "/"
HOME_PREFIX = "/" + "home" + "/"
WINDOWS_USERS_PATTERN = "[A-Za-z]:\\\\" + "Users" + "\\\\"
DETECTOR_PATTERN_LITERAL = "(" + USERS_PREFIX + "|" + HOME_PREFIX + "|" + WINDOWS_USERS_PATTERN + ")"
MEANINGFUL_HOME_PATH_HIT = "deadbeef:docs/example.md:12:C:" + "\\" + "Users" + "\\" + "alice" + "\\" + "private" + "\\" + "project"


def _remote_summary_base() -> dict[str, object]:
    return {
        "available": True,
        "repo": {
            "visibility": "public",
            "archived": False,
            "fork": False,
            "forks_count": 0,
            "default_branch": "main",
            "owner": {"login": "xiaojiou176-open", "type": "Organization"},
            "security_and_analysis": {
                "secret_scanning": {"status": "enabled"},
                "secret_scanning_push_protection": {"status": "enabled"},
                "dependabot_security_updates": {"status": "enabled"},
                "secret_scanning_non_provider_patterns": {"status": "enabled"},
                "secret_scanning_validity_checks": {"status": "enabled"},
            },
        },
        "branch_protection": {
            "enforce_admins": {"enabled": True},
            "allow_force_pushes": {"enabled": False},
            "allow_deletions": {"enabled": False},
            "required_linear_history": {"enabled": True},
            "required_conversation_resolution": {"enabled": True},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
        },
        "code_security_configuration": None,
        "releases": [{"tag_name": "v0.1.0"}],
        "secret_scanning_alerts": [],
        "security_advisories": [],
        "pull_requests": [],
    }


def test_is_meaningful_history_path_hit_ignores_detector_patterns_and_synthetic_fixture() -> None:
    assert not _is_meaningful_history_path_hit(
        "deadbeef:notes_recovery/core/pipeline.py:37:ABSOLUTE_PATH_PATTERN = re.compile("
        + 'r"('
        + USERS_PREFIX
        + "|"
        + HOME_PREFIX
        + "|"
        + WINDOWS_USERS_PATTERN
        + ')"'
        + ")"
    )
    assert not _is_meaningful_history_path_hit(
        "deadbeef:scripts/ci/check_public_safe_outputs.py:8:ABSOLUTE_PATH_PATTERN = re.compile("
        + 'r"('
        + USERS_PREFIX
        + "|"
        + HOME_PREFIX
        + "|"
        + WINDOWS_USERS_PATTERN
        + ')"'
        + ")"
    )
    assert not _is_meaningful_history_path_hit(
        'deadbeef:tests/test_public_safe_export.py:25:"python_executable": "'
        + USERS_PREFIX
        + 'demo/.venv/bin/python"'
    )
    assert _is_meaningful_history_path_hit(MEANINGFUL_HOME_PATH_HIT)


def test_evaluate_release_summary_treats_published_tags_as_notes() -> None:
    local_summary = {
        "tags": ["v0.1.0"],
        "tracked_fixture_paths": [],
        "largest_blobs": [],
        "history_path_hits": [],
        "lfs_status": "git-lfs unavailable",
        "lfs_entries": [],
    }

    evaluation = _evaluate_release_summary(
        local_summary,
        _remote_summary_base(),
        max_blob_bytes=1_000_000,
    )

    assert all("include them in release audit scope" not in item for item in evaluation["manual_review"])
    assert any("matched by published GitHub releases" in item for item in evaluation["notes"])


def test_evaluate_release_summary_ignores_only_synthetic_history_hits() -> None:
    local_summary = {
        "tags": [],
        "tracked_fixture_paths": [],
        "largest_blobs": [],
        "history_path_hits": [
            "deadbeef:notes_recovery/core/pipeline.py:37:ABSOLUTE_PATH_PATTERN = re.compile("
            + 'r"('
            + USERS_PREFIX
            + "|"
            + HOME_PREFIX
            + "|"
            + WINDOWS_USERS_PATTERN
            + ')"'
            + ")",
            "deadbeef:scripts/ci/check_public_safe_outputs.py:8:ABSOLUTE_PATH_PATTERN = re.compile("
            + 'r"('
            + USERS_PREFIX
            + "|"
            + HOME_PREFIX
            + "|"
            + WINDOWS_USERS_PATTERN
            + ')"'
            + ")",
        ],
        "lfs_status": "git-lfs unavailable",
        "lfs_entries": [],
    }

    evaluation = _evaluate_release_summary(
        local_summary,
        _remote_summary_base(),
        max_blob_bytes=1_000_000,
    )

    assert all("absolute path-like strings" not in item for item in evaluation["manual_review"])
    assert any("known detector patterns or synthetic fixtures" in item for item in evaluation["notes"])


def test_evaluate_release_summary_treats_enforced_code_security_configuration_as_authority() -> None:
    remote_summary = _remote_summary_base()
    remote_summary["repo"]["security_and_analysis"]["secret_scanning_non_provider_patterns"]["status"] = "disabled"
    remote_summary["repo"]["security_and_analysis"]["secret_scanning_validity_checks"]["status"] = "disabled"
    remote_summary["code_security_configuration"] = {
        "status": "enforced",
        "configuration": {
            "secret_scanning_non_provider_patterns": "enabled",
            "secret_scanning_validity_checks": "enabled",
        },
    }

    local_summary = {
        "tags": [],
        "tracked_fixture_paths": [],
        "largest_blobs": [],
        "history_path_hits": [],
        "lfs_status": "git-lfs unavailable",
        "lfs_entries": [],
    }

    evaluation = _evaluate_release_summary(
        local_summary,
        remote_summary,
        max_blob_bytes=1_000_000,
    )

    assert all("secret_scanning_non_provider_patterns" not in item for item in evaluation["manual_review"])
    assert all("secret_scanning_validity_checks" not in item for item in evaluation["manual_review"])
    assert any("code-security configuration status: enforced" in item for item in evaluation["notes"])


def test_evaluate_release_summary_treats_fully_merged_pr_history_as_notes() -> None:
    remote_summary = _remote_summary_base()
    remote_summary["pull_requests"] = [
        {
            "number": 1,
            "state": "MERGED",
            "title": "Merge governance closeout",
            "url": "https://github.com/xiaojiou176-open/noteyard/pull/1",
        }
    ]

    local_summary = {
        "tags": [],
        "tracked_fixture_paths": [],
        "largest_blobs": [],
        "history_path_hits": [],
        "lfs_status": "git-lfs unavailable",
        "lfs_entries": [],
    }

    evaluation = _evaluate_release_summary(
        local_summary,
        remote_summary,
        max_blob_bytes=1_000_000,
    )

    assert all("pull request" not in item for item in evaluation["manual_review"])
    assert any("fully merged" in item for item in evaluation["notes"])


def test_evaluate_release_summary_ignores_reviewed_closed_unmerged_pull_requests() -> None:
    remote_summary = _remote_summary_base()
    remote_summary["pull_requests"] = [
        {
            "number": 3,
            "state": "CLOSED",
            "title": "ci(deps): submit dependency snapshots for review support",
            "url": "https://github.com/xiaojiou176-open/noteyard/pull/3",
        },
        {
            "number": 9,
            "state": "CLOSED",
            "title": "fix: allow github-hosted squash merge identity",
            "url": "https://github.com/xiaojiou176-open/noteyard/pull/9",
        },
    ]

    local_summary = {
        "tags": [],
        "tracked_fixture_paths": [],
        "largest_blobs": [],
        "history_path_hits": [],
        "lfs_status": "git-lfs unavailable",
        "lfs_entries": [],
    }

    evaluation = _evaluate_release_summary(
        local_summary,
        remote_summary,
        max_blob_bytes=1_000_000,
    )

    assert all("closed unmerged pull request" not in item for item in evaluation["manual_review"])
    assert any("#3" in item and "#9" in item for item in evaluation["notes"])


def test_evaluate_release_summary_keeps_unknown_closed_unmerged_pull_requests_manual() -> None:
    remote_summary = _remote_summary_base()
    remote_summary["pull_requests"] = [
        {
            "number": 99,
            "state": "CLOSED",
            "title": "unknown closed pull request",
            "url": "https://github.com/xiaojiou176-open/noteyard/pull/99",
        }
    ]

    local_summary = {
        "tags": [],
        "tracked_fixture_paths": [],
        "largest_blobs": [],
        "history_path_hits": [],
        "lfs_status": "git-lfs unavailable",
        "lfs_entries": [],
    }

    evaluation = _evaluate_release_summary(
        local_summary,
        remote_summary,
        max_blob_bytes=1_000_000,
    )

    assert any("closed unmerged pull request" in item for item in evaluation["manual_review"])


def test_gh_json_treats_no_content_as_none(monkeypatch) -> None:
    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=["gh", "api", "/repos/example/no-content"],
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(release_readiness, "_run", fake_run)

    assert _gh_json(Path("/tmp/repo"), "/repos/example/no-content") is None
