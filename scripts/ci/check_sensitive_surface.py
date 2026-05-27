from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ABSOLUTE_PATH_PATTERN = re.compile(
    "|".join(
        (
            re.escape("/" + "Users" + "/"),
            re.escape("/" + "home" + "/"),
            r"[A-Za-z]:\\" + "Users" + r"\\",
        )
    )
)
GITHUB_NOREPLY_EMAIL_PATTERN = re.compile(
    r"(?:\d+\+)?[A-Za-z0-9][A-Za-z0-9._-]*@users\.noreply\.github\.com$"
)
LEGACY_MAINTAINER_NAME_PATTERNS = (
    re.compile(re.escape("Yifeng" + "[Terry]" + " Yu")),
    re.compile(re.escape("Yifeng" + " (Terry) " + "Yu")),
)
FORBIDDEN_TRACKED_PATH_PATTERNS = (
    re.compile(r"(^|/)\.env(\.[^/]+)?$"),
    re.compile(r"(^|/)\.runtime-cache(/|$)"),
    re.compile(r"(^|/)cache(/|$)"),
    re.compile(r"(^|/)\.cache(/|$)"),
    re.compile(r"(^|/)log(/|$)"),
    re.compile(r"(^|/)logs(/|$)"),
    re.compile(r"\.log$"),
    re.compile(r"\.(pem|key|p12|pfx|jks|keystore|crt|cer|der)$"),
    re.compile(r"(^|/)credentials\.json$"),
    re.compile(r"(^|/)secrets\.ya?ml$"),
    re.compile(r"\.(sqlite3?|db|sqlite-shm|sqlite-wal)$"),
    re.compile(r"\.(har|pcap)$"),
)
TRACKED_PATH_ALLOWLIST = (
    ".env.example",
    "tests/data/icloud_min.sqlite",
    "tests/data/legacy_min.sqlite",
)
ALLOWED_GITHUB_NOREPLY_EMAILS = {
    "repo-guardrail@users.noreply.github.com",
}
CANONICAL_PUBLIC_OWNER_NOREPLY_EMAIL = "xiaojiou176" + "@users.noreply.github.com"
ALLOWED_GITHUB_NOREPLY_EMAILS_BY_PATH = {
    ".claude-plugin/marketplace.json": {
        CANONICAL_PUBLIC_OWNER_NOREPLY_EMAIL,
    },
}


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


def _tracked_files(repo_root: Path) -> list[str]:
    return _git_lines(repo_root, "ls-files")


def _is_allowed_tracked_path(relative_path: str) -> bool:
    return relative_path in TRACKED_PATH_ALLOWLIST


def _is_allowed_noreply_email(email: str, relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    return (
        email in ALLOWED_GITHUB_NOREPLY_EMAILS
        or email.endswith("[bot]@users.noreply.github.com")
        or email in ALLOWED_GITHUB_NOREPLY_EMAILS_BY_PATH.get(normalized, set())
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def collect_sensitive_surface_errors(
    repo_root: Path,
    *,
    tracked_files: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    tracked = tracked_files if tracked_files is not None else _tracked_files(repo_root)

    for relative_path in tracked:
        normalized = relative_path.replace("\\", "/")
        path = repo_root / relative_path

        for pattern in FORBIDDEN_TRACKED_PATH_PATTERNS:
            if pattern.search(normalized) and not _is_allowed_tracked_path(normalized):
                errors.append(f"tracked sensitive artifact path detected: {normalized}")
                break

        if not path.exists() or not path.is_file():
            continue

        text = _read_text(path)
        if ABSOLUTE_PATH_PATTERN.search(text):
            errors.append(f"absolute path-like string found in tracked file: {normalized}")

        for pattern in LEGACY_MAINTAINER_NAME_PATTERNS:
            if pattern.search(text):
                errors.append(f"legacy maintainer identity found in tracked file: {normalized}")
                break

        for line_no, line in enumerate(text.splitlines(), start=1):
            for token in line.split():
                candidate = token.strip("`'\"(),[]{}<>")
                if not GITHUB_NOREPLY_EMAIL_PATTERN.fullmatch(candidate):
                    continue
                if _is_allowed_noreply_email(candidate, normalized):
                    continue
                errors.append(
                    "non-allowlisted GitHub noreply email found in tracked file: "
                    f"{normalized}:{line_no} -> {candidate}"
                )

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors = collect_sensitive_surface_errors(repo_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("sensitive surface check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
