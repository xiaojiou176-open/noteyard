from __future__ import annotations

import argparse
import os
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


GITHUB_SLUG_PATTERN = re.compile(
    r"(?:github\.com[:/])(?P<slug>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?$"
)


def _run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None


def _git_remote_slug(repo_root: Path) -> str | None:
    completed = _run(["git", "remote", "get-url", "origin"], cwd=repo_root)
    if not completed or completed.returncode != 0:
        return None
    remote_url = completed.stdout.strip()
    match = GITHUB_SLUG_PATTERN.search(remote_url)
    if not match:
        return None
    return match.group("slug")


def _gh_json(repo_root: Path, endpoint: str) -> Any | None:
    for attempt in range(3):
        completed = _run(["gh", "api", endpoint], cwd=repo_root)
        if completed and completed.returncode == 0:
            if not completed.stdout.strip():
                return None
            return json.loads(completed.stdout)
        if attempt < 2:
            time.sleep(0.5)
    return None


def collect_github_security_alert_errors(
    repo_root: Path,
    *,
    repo_slug: str | None = None,
    allow_secret_scanning_fallback: bool = False,
) -> list[str]:
    errors: list[str] = []
    slug = repo_slug or _git_remote_slug(repo_root)
    if not slug:
        return ["unable to detect canonical GitHub repository slug from origin remote"]

    secret_alerts = _gh_json(repo_root, f"/repos/{slug}/secret-scanning/alerts?per_page=100")
    if secret_alerts is None:
        if allow_secret_scanning_fallback:
            repo_json = _gh_json(repo_root, f"/repos/{slug}")
            status = (
                repo_json.get("security_and_analysis", {})
                .get("secret_scanning", {})
                .get("status")
                if isinstance(repo_json, dict)
                else None
            )
            if status == "disabled":
                errors.append(
                    "unable to query GitHub secret-scanning alerts and secret scanning is not confirmed enabled"
                )
        else:
            errors.append("unable to query GitHub secret-scanning alerts")
    elif secret_alerts:
        errors.append(f"GitHub secret-scanning open alerts must be zero, got {len(secret_alerts)}")

    code_alerts = _gh_json(repo_root, f"/repos/{slug}/code-scanning/alerts?state=open&per_page=100")
    if code_alerts is None:
        errors.append("unable to query GitHub code-scanning open alerts")
    elif code_alerts:
        errors.append(f"GitHub code-scanning open alerts must be zero, got {len(code_alerts)}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None)
    parser.add_argument(
        "--allow-secret-scanning-fallback",
        action="store_true",
        help="allow CI to fall back to repository secret-scanning status when the alerts endpoint is unavailable",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    allow_secret_scanning_fallback = (
        args.allow_secret_scanning_fallback
        or os.environ.get("NOTES_RECOVER_ALLOW_SECRET_SCANNING_FALLBACK") == "1"
        or bool(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    )
    errors = collect_github_security_alert_errors(
        repo_root,
        repo_slug=args.repo,
        allow_secret_scanning_fallback=allow_secret_scanning_fallback,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("github security alerts check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
