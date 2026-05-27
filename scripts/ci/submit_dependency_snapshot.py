from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import tomllib


PACKAGE_NAME_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
GITHUB_SLUG_PATTERN = re.compile(
    r"(?:github\.com[:/])(?P<slug>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?$"
)
DETECTOR_NAME = "noteyard-python-environment"
DETECTOR_VERSION = "1.0.0"
DEFAULT_MANIFEST_KEY = "python-environment"
DEVELOPMENT_GROUPS = {"dev"}


@dataclass(frozen=True)
class InstalledPackage:
    name: str
    version: str

    @property
    def normalized_name(self) -> str:
        return normalize_package_name(self.name)


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def extract_requirement_name(requirement: str) -> str | None:
    match = PACKAGE_NAME_PATTERN.match(requirement)
    if not match:
        return None
    return normalize_package_name(match.group(1))


def load_direct_dependency_scopes(pyproject_path: Path) -> dict[str, str]:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    scopes: dict[str, str] = {}

    for requirement in project.get("dependencies", []):
        name = extract_requirement_name(requirement)
        if name:
            scopes[name] = "runtime"

    for group_name, requirements in project.get("optional-dependencies", {}).items():
        scope = "development" if normalize_package_name(group_name) in DEVELOPMENT_GROUPS else "runtime"
        for requirement in requirements:
            name = extract_requirement_name(requirement)
            if name:
                scopes[name] = scope

    return scopes


def collect_installed_packages(project_name: str) -> list[InstalledPackage]:
    packages: dict[str, InstalledPackage] = {}
    project_normalized = normalize_package_name(project_name)

    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        version = distribution.version
        if not name or not version:
            continue
        normalized = normalize_package_name(name)
        if normalized == project_normalized:
            continue
        packages[normalized] = InstalledPackage(name=name, version=version)

    return sorted(packages.values(), key=lambda package: package.normalized_name)


def build_resolved_packages(
    packages: list[InstalledPackage],
    direct_scopes: dict[str, str],
) -> dict[str, dict[str, str]]:
    resolved: dict[str, dict[str, str]] = {}

    for package in packages:
        package_url = (
            f"pkg:pypi/{urllib.parse.quote(package.normalized_name, safe='-')}@"
            f"{urllib.parse.quote(package.version, safe='.+!-_')}"
        )
        item: dict[str, str] = {"package_url": package_url}
        if package.normalized_name in direct_scopes:
            item["relationship"] = "direct"
            item["scope"] = direct_scopes[package.normalized_name]
        else:
            item["relationship"] = "indirect"
        resolved[package.normalized_name] = item

    return resolved


def detect_repo_slug(repo_root: Path) -> str | None:
    repository = os.environ.get("GITHUB_REPOSITORY")
    if repository:
        return repository

    git_config = repo_root / ".git" / "config"
    if not git_config.exists():
        return None

    for line in git_config.read_text(encoding="utf-8").splitlines():
        if "url =" not in line:
            continue
        match = GITHUB_SLUG_PATTERN.search(line)
        if match:
            return match.group("slug")
    return None


def resolve_local_sha_and_ref(repo_root: Path) -> tuple[str, str]:
    try:
        sha = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True)
            .strip()
        )
        branch = (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_root,
                text=True,
            )
            .strip()
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("unable to resolve local git sha/ref for dependency snapshot submission") from error

    ref_branch = "main" if branch == "HEAD" else branch
    return sha[:40], f"refs/heads/{ref_branch}"


def resolve_sha_and_ref(repo_root: Path) -> tuple[str, str]:
    sha = os.environ.get("GITHUB_SHA", "").strip()
    ref = os.environ.get("GITHUB_REF", "").strip()
    event_name = os.environ.get("GITHUB_EVENT_NAME", "").strip()
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()

    if event_name == "pull_request" and event_path:
        try:
            event_payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            event_payload = {}
        pull_request = event_payload.get("pull_request", {})
        head = pull_request.get("head", {})
        sha = str(head.get("sha") or sha).strip()
        head_ref = str(head.get("ref") or "").strip()
        if head_ref:
            ref = f"refs/heads/{head_ref}"

    if not sha or not ref:
        return resolve_local_sha_and_ref(repo_root)

    return sha[:40], ref


def build_snapshot(
    *,
    repo_slug: str,
    project_name: str,
    packages: list[InstalledPackage],
    direct_scopes: dict[str, str],
    sha: str,
    ref: str,
) -> dict[str, Any]:
    run_id = os.environ.get("GITHUB_RUN_ID", "local-run")
    workflow = os.environ.get("GITHUB_WORKFLOW", "local")
    job_name = os.environ.get("GITHUB_JOB", "dependency-snapshot")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    job_url = f"{server_url}/{repo_slug}/actions/runs/{run_id}"
    scanned = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    return {
        "version": 0,
        "sha": sha,
        "ref": ref,
        "job": {
            "id": run_id,
            "correlator": f"{workflow} {job_name} python-full-environment",
            "html_url": job_url,
        },
        "detector": {
            "name": DETECTOR_NAME,
            "version": DETECTOR_VERSION,
            "url": f"{server_url}/{repo_slug}",
        },
        "metadata": {
            "project": project_name,
            "environment": "full-validation",
        },
        "manifests": {
            DEFAULT_MANIFEST_KEY: {
                "name": f"{project_name} python environment",
                "file": {"source_location": "pyproject.toml"},
                "resolved": build_resolved_packages(packages, direct_scopes),
            }
        },
        "scanned": scanned,
    }


def submit_snapshot(repo_slug: str, snapshot: dict[str, Any], token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo_slug}/dependency-graph/snapshots",
        data=json.dumps(snapshot).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2026-03-10",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"dependency snapshot submission failed: HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"dependency snapshot submission failed: {error.reason}") from error

    return json.loads(response_body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=None, help="GitHub repository slug such as owner/repo")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the snapshot payload instead of submitting it",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.exists():
        print("missing pyproject.toml", file=sys.stderr)
        return 1

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project_name = str(pyproject.get("project", {}).get("name", "")).strip()
    if not project_name:
        print("pyproject.toml is missing project.name", file=sys.stderr)
        return 1

    repo_slug = args.repo or detect_repo_slug(repo_root)
    if not repo_slug:
        print("unable to determine GitHub repository slug", file=sys.stderr)
        return 1

    try:
        sha, ref = resolve_sha_and_ref(repo_root)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    packages = collect_installed_packages(project_name)
    if not packages:
        print("no installed packages found for dependency snapshot submission", file=sys.stderr)
        return 1

    snapshot = build_snapshot(
        repo_slug=repo_slug,
        project_name=project_name,
        packages=packages,
        direct_scopes=load_direct_dependency_scopes(pyproject_path),
        sha=sha,
        ref=ref,
    )

    if args.dry_run:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 0

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("missing GITHUB_TOKEN or GH_TOKEN for dependency snapshot submission", file=sys.stderr)
        return 1

    try:
        response = submit_snapshot(repo_slug, snapshot, token)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(
        "dependency snapshot submitted",
        json.dumps(
            {
                "id": response.get("id"),
                "result": response.get("result"),
                "message": response.get("message"),
            },
            sort_keys=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
