from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REQUIRED_GITIGNORE_MARKERS = (
    ".agents/",
    ".agent/",
    ".codex/",
    ".claude/",
    ".runtime-cache/",
    "log/",
    "logs/",
    "*.log",
    ".env",
    ".env.*",
    "!.env.example",
    "*.pem",
    "*.key",
    "*.p12",
    "*.jks",
    "*.keystore",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "secrets.yml",
    "secrets.yaml",
)

REQUIRED_PRECOMMIT_TOKENS = (
    "default_install_hook_types",
    "pre-push",
    "gitleaks",
    "git-secrets",
    "actionlint workflow lint",
    "check_commit_identity.py",
    "check_sensitive_surface.py",
    "check_host_safety_contract.py",
    "check_repo_hygiene.py --mode hygiene",
    "check_repo_hygiene.py --mode open-source-boundary",
    "check_runtime_hygiene.py",
    "check_english_surface.py",
    "check_public_safe_outputs.py",
    "baseline-smoke",
)

REQUIRED_WORKFLOW_TOKENS = (
    "check_commit_identity.py",
    "check_sensitive_surface.py",
    "check_github_security_alerts.py",
    "check_pypi_publish_readiness.py",
    "check_host_safety_contract.py",
    "rhysd/actionlint@",
    "trufflehog git",
    "zizmorcore/zizmor-action@",
    "trivy fs",
    "persist-credentials: false",
)

REQUIRED_DEPENDABOT_TOKENS = (
    'package-ecosystem: "pip"',
    'package-ecosystem: "github-actions"',
    'interval: "daily"',
    'time: "09:00"',
    'timezone: "America/Los_Angeles"',
)

TRACKED_NOISE_PATTERNS = (
    re.compile(r"(^|/)\.DS_Store$"),
    re.compile(r"(^|/)__pycache__(/|$)"),
    re.compile(r"\.pyc$"),
    re.compile(r"(^|/)\.pytest_cache(/|$)"),
    re.compile(r"(^|/).+\.egg-info(/|$)"),
)

PINNED_ACTION_PATTERN = re.compile(r"^\s*-\s+uses:\s+([^@\s]+)@([0-9a-f]{40})\s*$")

OPEN_SOURCE_BOUNDARY_TOKENS = (
    "git history",
    "pull request diffs",
    "forks",
    "mirrors",
    "downloaded clones",
    "branch protection",
    "secret scanning",
    "hosting settings",
)

REQUIRED_ENV_EXAMPLE_TOKENS = (
    "NOTES_CASE_HMAC_KEY",
    "NOTES_CASE_PGP_KEY",
    "NOTES_CASE_PGP_HOME",
)

REQUIRED_COMMUNITY_FILES = (
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/pull_request_template.md",
    "SUPPORT.md",
    "AGENTS.md",
    "CLAUDE.md",
)


def _git_lines(repo_root: Path, *args: str) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def collect_hygiene_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.exists():
        errors.append("missing .gitignore")
        return errors

    gitignore_text = gitignore_path.read_text(encoding="utf-8")
    for marker in REQUIRED_GITIGNORE_MARKERS:
        if marker not in gitignore_text:
            errors.append(f".gitignore is missing required marker: {marker}")

    precommit_path = repo_root / ".pre-commit-config.yaml"
    if not precommit_path.exists():
        errors.append("missing .pre-commit-config.yaml")
    else:
        precommit_text = precommit_path.read_text(encoding="utf-8")
        for token in REQUIRED_PRECOMMIT_TOKENS:
            if token not in precommit_text:
                errors.append(f".pre-commit-config.yaml is missing required token: {token}")

    gitleaks_config_path = repo_root / ".gitleaks.toml"
    if not gitleaks_config_path.exists():
        errors.append("missing .gitleaks.toml")

    dependabot_path = repo_root / ".github" / "dependabot.yml"
    if not dependabot_path.exists():
        errors.append("missing .github/dependabot.yml")
    else:
        dependabot_text = dependabot_path.read_text(encoding="utf-8")
        for token in REQUIRED_DEPENDABOT_TOKENS:
            if token not in dependabot_text:
                errors.append(f".github/dependabot.yml is missing required token: {token}")

    env_example_path = repo_root / ".env.example"
    if not env_example_path.exists():
        errors.append("missing .env.example")
    else:
        env_example_text = env_example_path.read_text(encoding="utf-8")
        for token in REQUIRED_ENV_EXAMPLE_TOKENS:
            if token not in env_example_text:
                errors.append(f".env.example is missing required token: {token}")

    tracked_files = _git_lines(repo_root, "ls-files")
    for tracked in tracked_files:
        if any(pattern.search(tracked) for pattern in TRACKED_NOISE_PATTERNS):
            errors.append(f"tracked repository noise detected: {tracked}")

    return errors


def collect_open_source_boundary_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    for relative_path in REQUIRED_COMMUNITY_FILES:
        if not (repo_root / relative_path).exists():
            errors.append(f"missing {relative_path}")

    security_path = repo_root / "SECURITY.md"
    if not security_path.exists():
        errors.append("missing SECURITY.md")
    else:
        security_text = security_path.read_text(encoding="utf-8")
        if "GitHub Security Advisories" not in security_text:
            errors.append("SECURITY.md should mention GitHub Security Advisories")
        if "hosting profile" in security_text:
            errors.append("SECURITY.md should not rely on a hosting-profile fallback")
        if "single-maintainer" not in security_text and "single-maintainer owner" not in security_text:
            errors.append("SECURITY.md should declare the current owner boundary")

    codeowners_path = repo_root / "CODEOWNERS"
    if not codeowners_path.exists():
        errors.append("missing CODEOWNERS")

    readme_path = repo_root / "README.md"
    if not readme_path.exists():
        errors.append("missing README.md")
    else:
        readme_text = readme_path.read_text(encoding="utf-8").casefold()
        for token in OPEN_SOURCE_BOUNDARY_TOKENS:
            if token.casefold() not in readme_text:
                errors.append(f"README.md is missing boundary token: {token}")
        if "check_release_readiness.py" not in readme_text:
            errors.append("README.md should mention check_release_readiness.py")
        for token in ("required pull request reviews", "xiaojiou176", "opt-in integrations"):
            if token.casefold() not in readme_text:
                errors.append(f"README.md is missing boundary token: {token}")

    provenance_path = repo_root / "tests" / "data" / "README.md"
    if not provenance_path.exists():
        errors.append("missing tests/data/README.md provenance note")
    else:
        provenance_text = provenance_path.read_text(encoding="utf-8")
        for token in ("synthetic", "not exported from a live Apple Notes account", "verification inputs"):
            if token not in provenance_text:
                errors.append(f"tests/data/README.md is missing provenance token: {token}")

    workflow_path = repo_root / ".github" / "workflows" / "ci.yml"
    if not workflow_path.exists():
        errors.append("missing .github/workflows/ci.yml")
    else:
        workflow_text = workflow_path.read_text(encoding="utf-8")
        if "permissions:" not in workflow_text:
            errors.append("workflow is missing explicit permissions")
        for token in REQUIRED_WORKFLOW_TOKENS:
            if token not in workflow_text:
                errors.append(f"workflow is missing required token: {token}")
        for line in workflow_text.splitlines():
            if "uses:" not in line:
                continue
            if "actions/checkout" in line or "actions/setup-python" in line:
                if not PINNED_ACTION_PATTERN.match(line):
                    errors.append(f"workflow action is not SHA pinned: {line.strip()}")

    release_audit_path = repo_root / "scripts" / "ci" / "check_release_readiness.py"
    if not release_audit_path.exists():
        errors.append("missing scripts/ci/check_release_readiness.py")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("hygiene", "open-source-boundary"),
        required=True,
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    if args.mode == "hygiene":
        errors = collect_hygiene_errors(repo_root)
    else:
        errors = collect_open_source_boundary_errors(repo_root)

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"{args.mode} check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
