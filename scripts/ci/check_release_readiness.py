from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


GITHUB_SLUG_PATTERN = re.compile(
    r"(?:github\.com[:/])(?P<slug>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?$"
)
ABSOLUTE_PATH_PATTERN = re.compile(
    "|".join(
        (
            re.escape("/" + "Users" + "/"),
            re.escape("/" + "home" + "/"),
            r"[A-Za-z]:\\" + "Users" + r"\\",
        )
    )
)
REQUIRED_SECURITY_STATUSES = (
    ("secret_scanning", "GitHub Secret Scanning"),
    ("secret_scanning_push_protection", "GitHub Push Protection"),
    ("dependabot_security_updates", "Dependabot security updates"),
)
SELF_AUDIT_IGNORED_PATHS = {
    "scripts/ci/check_release_readiness.py",
}
SAFE_HISTORY_PATH_HIT_RULES = (
    (
        "notes_recovery/core/pipeline.py",
        "ABSOLUTE_PATH_PATTERN = re.compile",
    ),
    (
        "scripts/ci/check_public_safe_outputs.py",
        "ABSOLUTE_PATH_PATTERN = re.compile",
    ),
    (
        "tests/test_public_safe_export.py",
        "/" + "Users" + "/demo/.venv/bin/python",
    ),
    (
        "tests/test_release_readiness.py",
        "deadbeef:",
    ),
)
REVIEWED_CLOSED_UNMERGED_PULL_REQUESTS = {
    1: "Reviewed closed dependabot CodeQL bump; current workflow state intentionally diverged from this abandoned update branch.",
    3: "Reviewed closed dependency snapshot PR; superseded by merged PR #7.",
    4: "Reviewed closed proof/front-door PR; superseded by merged PR #5 with the same patch set.",
    6: "Reviewed closed dependency snapshot refresh PR; superseded by merged PR #7.",
    9: "Reviewed closed hosted-squash identity hotfix PR; superseded by merged PR #12.",
    10: "Reviewed closed hosted-squash identity hotfix PR; superseded by merged PR #12.",
    11: "Reviewed closed hosted-squash identity hotfix PR; superseded by merged PR #12.",
}


def _run(
    args: list[str],
    *,
    cwd: Path,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None


def _git_lines(repo_root: Path, *args: str) -> list[str]:
    completed = _run(["git", *args], cwd=repo_root)
    if not completed or completed.returncode != 0:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _gh_json(repo_root: Path, endpoint: str) -> Any | None:
    completed = _run(["gh", "api", endpoint], cwd=repo_root)
    if not completed or completed.returncode != 0:
        return None
    if not completed.stdout.strip():
        return None
    return json.loads(completed.stdout)


def _gh_prs(repo_root: Path, repo_slug: str) -> list[dict[str, Any]] | None:
    completed = _run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo_slug,
            "--state",
            "all",
            "--limit",
            "100",
            "--json",
            "number,state,title,url",
        ],
        cwd=repo_root,
    )
    if not completed or completed.returncode != 0:
        return None
    return json.loads(completed.stdout)


def _parse_github_slug(remote_url: str) -> str | None:
    match = GITHUB_SLUG_PATTERN.search(remote_url.strip())
    if not match:
        return None
    return match.group("slug")


def _detect_repo_slug(repo_root: Path, explicit_repo: str | None) -> str | None:
    if explicit_repo:
        return explicit_repo

    remote_url = _git_lines(repo_root, "remote", "get-url", "origin")
    if not remote_url:
        return None
    return _parse_github_slug(remote_url[0])


def _collect_largest_blobs(repo_root: Path, limit: int) -> list[dict[str, Any]]:
    rev_list = _run(["git", "rev-list", "--objects", "--all"], cwd=repo_root)
    if not rev_list or rev_list.returncode != 0 or not rev_list.stdout.strip():
        return []

    batch = _run(
        [
            "git",
            "cat-file",
            "--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)",
        ],
        cwd=repo_root,
        input_text=rev_list.stdout,
    )
    if not batch or batch.returncode != 0:
        return []

    blobs: list[dict[str, Any]] = []
    for line in batch.stdout.splitlines():
        parts = line.split(" ", 3)
        if len(parts) != 4:
            continue
        object_type, _, size_text, path = parts
        if object_type != "blob":
            continue
        try:
            size = int(size_text)
        except ValueError:
            continue
        blobs.append({"path": path, "size": size})

    blobs.sort(key=lambda item: item["size"], reverse=True)
    return blobs[:limit]


def _collect_history_path_hits(repo_root: Path, limit: int) -> list[str]:
    hits: list[str] = []
    seen: set[str] = set()

    for rev in _git_lines(repo_root, "rev-list", "--all"):
        completed = _run(
            ["git", "grep", "-nE", ABSOLUTE_PATH_PATTERN.pattern, rev],
            cwd=repo_root,
        )
        if not completed or completed.returncode not in (0, 1):
            continue
        for line in completed.stdout.splitlines():
            parts = line.split(":", 3)
            if len(parts) >= 2 and parts[1] in SELF_AUDIT_IGNORED_PATHS:
                continue
            if line in seen:
                continue
            seen.add(line)
            hits.append(line)
            if len(hits) >= limit:
                return hits

    return hits


def _is_meaningful_history_path_hit(line: str) -> bool:
    parts = line.split(":", 3)
    if len(parts) != 4:
        return True

    _, path, _, content = parts
    for safe_path, safe_token in SAFE_HISTORY_PATH_HIT_RULES:
        if path == safe_path and safe_token in content:
            return False
    return True


def _meaningful_history_path_hits(lines: list[str]) -> list[str]:
    return [line for line in lines if _is_meaningful_history_path_hit(line)]


def _is_reviewed_closed_unmerged_pr(pr: dict[str, Any]) -> bool:
    number = pr.get("number")
    return isinstance(number, int) and number in REVIEWED_CLOSED_UNMERGED_PULL_REQUESTS


def _collect_local_summary(repo_root: Path, history_limit: int, blob_limit: int) -> dict[str, Any]:
    lfs_completed = _run(["git", "lfs", "ls-files"], cwd=repo_root)
    if not lfs_completed:
        lfs_status = "git-lfs unavailable"
        lfs_entries: list[str] = []
    elif lfs_completed.returncode == 0:
        lfs_entries = [line for line in lfs_completed.stdout.splitlines() if line.strip()]
        lfs_status = "entries present" if lfs_entries else "no lfs-tracked files"
    else:
        lfs_entries = []
        lfs_status = (lfs_completed.stderr or lfs_completed.stdout).strip() or "git-lfs unavailable"

    return {
        "tags": _git_lines(repo_root, "tag", "--list"),
        "tracked_fixture_paths": _git_lines(repo_root, "ls-files", "tests/data"),
        "largest_blobs": _collect_largest_blobs(repo_root, blob_limit),
        "history_path_hits": _collect_history_path_hits(repo_root, history_limit),
        "lfs_status": lfs_status,
        "lfs_entries": lfs_entries,
    }


def _collect_remote_summary(repo_root: Path, repo_slug: str | None) -> dict[str, Any]:
    if not repo_slug:
        return {"available": False, "reason": "GitHub repo slug not detected"}

    repo_json = _gh_json(repo_root, f"/repos/{repo_slug}")
    if repo_json is None:
        return {"available": False, "reason": "gh api repo lookup failed", "repo_slug": repo_slug}

    default_branch = repo_json.get("default_branch", "main")
    return {
        "available": True,
        "repo_slug": repo_slug,
        "repo": repo_json,
        "branch_protection": _gh_json(repo_root, f"/repos/{repo_slug}/branches/{default_branch}/protection"),
        "code_security_configuration": _gh_json(
            repo_root,
            f"/repos/{repo_slug}/code-security-configuration",
        ),
        "releases": _gh_json(repo_root, f"/repos/{repo_slug}/releases?per_page=100"),
        "secret_scanning_alerts": _gh_json(repo_root, f"/repos/{repo_slug}/secret-scanning/alerts?per_page=20"),
        "security_advisories": _gh_json(repo_root, f"/repos/{repo_slug}/security-advisories?per_page=20"),
        "pull_requests": _gh_prs(repo_root, repo_slug),
    }


def _evaluate_release_summary(
    local_summary: dict[str, Any],
    remote_summary: dict[str, Any],
    *,
    max_blob_bytes: int,
) -> dict[str, list[str]]:
    blockers: list[str] = []
    manual_review: list[str] = []
    notes: list[str] = []

    tags = local_summary["tags"]
    if tags:
        releases = remote_summary.get("releases")
        if isinstance(releases, list):
            release_tags = {
                item.get("tag_name")
                for item in releases
                if isinstance(item, dict) and item.get("tag_name")
            }
            unmatched_tags = [tag for tag in tags if tag not in release_tags]
            if unmatched_tags:
                manual_review.append(
                    "Local git history has tag(s) without matching GitHub releases: "
                    + ", ".join(unmatched_tags)
                    + "."
                )
            else:
                notes.append("Local git tags are matched by published GitHub releases: " + ", ".join(tags))
        else:
            manual_review.append(f"Local git history has {len(tags)} tag(s); include them in release audit scope.")
    else:
        notes.append("Local git history has no tags.")

    largest_blobs = local_summary["largest_blobs"]
    if largest_blobs and largest_blobs[0]["size"] > max_blob_bytes:
        blockers.append(
            "Local git history contains blobs above the release threshold: "
            + ", ".join(f'{item["path"]} ({item["size"]} bytes)' for item in largest_blobs[:3])
        )
    elif largest_blobs:
        notes.append(
            "Largest tracked history blobs stay within the current release threshold; largest is "
            f'{largest_blobs[0]["path"]} ({largest_blobs[0]["size"]} bytes).'
        )

    history_path_hits = local_summary["history_path_hits"]
    meaningful_history_hits = _meaningful_history_path_hits(history_path_hits)
    if meaningful_history_hits:
        manual_review.append(
            "Git history still contains absolute path-like strings; review whether they are synthetic or require history cleanup."
        )
    elif history_path_hits:
        notes.append("Absolute path-like history hits are limited to known detector patterns or synthetic fixtures.")
    else:
        notes.append("No absolute path-like strings were found in sampled git history searches.")

    if local_summary["lfs_entries"]:
        manual_review.append("git-lfs entries exist; verify they are safe for public redistribution.")
    else:
        notes.append(f"LFS status: {local_summary['lfs_status']}.")

    fixture_paths = local_summary["tracked_fixture_paths"]
    if fixture_paths:
        notes.append("Tracked test fixtures remain limited to: " + ", ".join(fixture_paths))

    if not remote_summary.get("available"):
        manual_review.append(
            "GitHub remote checks were unavailable; run the release audit again with a readable canonical GitHub repo."
        )
        return {"blockers": blockers, "manual_review": manual_review, "notes": notes}

    repo = remote_summary["repo"]
    owner = repo.get("owner", {})
    code_security_configuration = remote_summary.get("code_security_configuration")
    notes.append(
        "GitHub repo state: "
        f"visibility={repo.get('visibility')}, archived={repo.get('archived')}, "
        f"fork={repo.get('fork')}, forks={repo.get('forks_count')}, "
        f"default_branch={repo.get('default_branch')}."
    )

    if owner.get("login") != "xiaojiou176-open" or owner.get("type") != "Organization":
        blockers.append(
            "The canonical GitHub repository is not owned by the expected xiaojiou176-open organization."
        )
    else:
        notes.append("The canonical GitHub repository is owned by the expected xiaojiou176-open organization.")

    if repo.get("fork"):
        blockers.append("The canonical GitHub repository is itself a fork; confirm public positioning before release.")

    if repo.get("forks_count", 0) > 0:
        manual_review.append("The canonical GitHub repository already has forks; repo-side cleanup cannot retract them.")
    else:
        notes.append("The canonical GitHub repository currently has zero forks.")

    security = repo.get("security_and_analysis", {})

    config_status = None
    config_payload = None
    if isinstance(code_security_configuration, dict):
        config_status = code_security_configuration.get("status")
        config_payload = code_security_configuration.get("configuration")
        if config_status:
            notes.append(f"Repository code-security configuration status: {config_status}.")

    for key, label in REQUIRED_SECURITY_STATUSES:
        if security.get(key, {}).get("status") != "enabled":
            blockers.append(f"{label} is not enabled on the canonical GitHub repository.")

    for key in ("secret_scanning_non_provider_patterns", "secret_scanning_validity_checks"):
        status = security.get(key, {}).get("status")
        if status and status != "enabled":
            if (
                config_status == "enforced"
                and isinstance(config_payload, dict)
                and config_payload.get(key) == "enabled"
            ):
                notes.append(
                    f"GitHub setting {key} is enforced as enabled by the applied code-security configuration, "
                    f"even though the repository `security_and_analysis` field still reads {status}."
                )
            else:
                manual_review.append(f"GitHub setting {key} remains {status}; treat it as platform-limited unless you can enable it.")

    protection = remote_summary["branch_protection"]
    if not protection:
        blockers.append("Branch protection is missing or unreadable on the default branch.")
    else:
        if not protection.get("enforce_admins", {}).get("enabled"):
            blockers.append("Branch protection does not enforce admin protections.")
        if protection.get("allow_force_pushes", {}).get("enabled"):
            blockers.append("Branch protection still allows force pushes.")
        if protection.get("allow_deletions", {}).get("enabled"):
            blockers.append("Branch protection still allows branch deletions.")
        if not protection.get("required_linear_history", {}).get("enabled"):
            manual_review.append("Branch protection does not require linear history.")
        if not protection.get("required_conversation_resolution", {}).get("enabled"):
            manual_review.append("Branch protection does not require conversation resolution.")
        review_settings = protection.get("required_pull_request_reviews")
        if not review_settings:
            blockers.append("Branch protection does not require pull request reviews.")
        elif review_settings.get("required_approving_review_count") != 1:
            blockers.append("Branch protection review policy must require exactly 1 approving review.")

    alerts = remote_summary["secret_scanning_alerts"]
    if alerts is None:
        manual_review.append("Secret scanning alerts could not be queried from GitHub.")
    elif alerts:
        blockers.append(f"GitHub Secret Scanning currently reports {len(alerts)} alert(s).")
    else:
        notes.append("GitHub Secret Scanning is enabled and currently reports zero alerts.")

    advisories = remote_summary["security_advisories"]
    if advisories is None:
        manual_review.append("GitHub Security Advisories could not be queried from GitHub.")
    else:
        notes.append(f"GitHub Security Advisories endpoint is readable and currently returns {len(advisories)} advisory record(s).")

    pull_requests = remote_summary["pull_requests"]
    if pull_requests is None:
        manual_review.append("GitHub pull request history could not be queried from GitHub.")
    elif pull_requests:
        open_pull_requests = [
            pr for pr in pull_requests if isinstance(pr, dict) and pr.get("state") == "OPEN"
        ]
        closed_unmerged_pull_requests = [
            pr for pr in pull_requests if isinstance(pr, dict) and pr.get("state") == "CLOSED"
        ]
        reviewed_closed_unmerged_pull_requests = [
            pr for pr in closed_unmerged_pull_requests if _is_reviewed_closed_unmerged_pr(pr)
        ]
        unresolved_closed_unmerged_pull_requests = [
            pr for pr in closed_unmerged_pull_requests if not _is_reviewed_closed_unmerged_pr(pr)
        ]
        merged_pull_requests = [
            pr for pr in pull_requests if isinstance(pr, dict) and pr.get("state") == "MERGED"
        ]

        if open_pull_requests:
            manual_review.append(
                "GitHub repository currently has "
                f"{len(open_pull_requests)} open pull request(s); review or close them before claiming full publication cleanup."
            )
        if unresolved_closed_unmerged_pull_requests:
            manual_review.append(
                "GitHub repository has "
                f"{len(unresolved_closed_unmerged_pull_requests)} closed unmerged pull request(s); review them before claiming full publication cleanup."
            )
        elif reviewed_closed_unmerged_pull_requests:
            reviewed_numbers = ", ".join(
                f"#{pr['number']}" for pr in reviewed_closed_unmerged_pull_requests if isinstance(pr.get("number"), int)
            )
            notes.append(
                "Closed unmerged pull requests already reviewed and accepted as superseded history: "
                f"{reviewed_numbers}."
            )
        if merged_pull_requests and not open_pull_requests and not closed_unmerged_pull_requests:
            notes.append(
                "GitHub repository pull request history is fully merged "
                f"({len(merged_pull_requests)} merged pull request(s))."
            )
    else:
        notes.append("GitHub repository currently has zero pull requests.")

    return {"blockers": blockers, "manual_review": manual_review, "notes": notes}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", help="GitHub owner/name. Defaults to origin remote if detectable.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable text.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when release blockers are present.")
    parser.add_argument(
        "--max-blob-bytes",
        type=int,
        default=1_000_000,
        help="Warn as a blocker when the largest tracked history blob exceeds this size.",
    )
    parser.add_argument(
        "--history-hit-limit",
        type=int,
        default=20,
        help="Maximum number of absolute path-like history hits to capture.",
    )
    parser.add_argument(
        "--blob-limit",
        type=int,
        default=10,
        help="Number of largest blobs to include in the report.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    repo_slug = _detect_repo_slug(repo_root, args.repo)
    local_summary = _collect_local_summary(
        repo_root,
        history_limit=args.history_hit_limit,
        blob_limit=args.blob_limit,
    )
    remote_summary = _collect_remote_summary(repo_root, repo_slug)
    evaluation = _evaluate_release_summary(
        local_summary,
        remote_summary,
        max_blob_bytes=args.max_blob_bytes,
    )

    report = {
        "repo_root": str(repo_root),
        "repo_slug": repo_slug,
        "local": local_summary,
        "remote": remote_summary,
        "evaluation": evaluation,
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Release readiness audit")
        print(f"- Repo root: {repo_root}")
        print(f"- Repo slug: {repo_slug or 'unavailable'}")
        print(f"- Blockers: {len(evaluation['blockers'])}")
        print(f"- Manual review items: {len(evaluation['manual_review'])}")
        print(f"- Notes: {len(evaluation['notes'])}")
        for label, items in (
            ("Blockers", evaluation["blockers"]),
            ("Manual review", evaluation["manual_review"]),
            ("Notes", evaluation["notes"]),
        ):
            print(f"\n{label}:")
            if not items:
                print("- none")
                continue
            for item in items:
                print(f"- {item}")

    if args.strict and evaluation["blockers"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
