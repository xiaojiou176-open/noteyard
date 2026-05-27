from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


CONFIG_NAME_EXAMPLE = "Yifeng" + "[Terry]" + " Yu"
CONFIG_EMAIL_EXAMPLE = "125581657+" + "xiaojiou176" + "@users.noreply.github.com"
LEGACY_NAME_EXAMPLE = "repo-guardrail"
LEGACY_PERSONAL_NAME_EXAMPLES = {
    "xiaojiou176",
}
LEGACY_PERSONAL_EMAILS = {
    "xiaojiou176" + "@users.noreply.github.com",
}
DEPENDABOT_NAME = "dependabot[bot]"
DEPENDABOT_EMAILS = {
    "49699333+dependabot[bot]@users.noreply.github.com",
}
GITHUB_NAME = "GitHub"
GITHUB_EMAIL = "noreply@github.com"
NOREPLY_EMAIL_PATTERN = re.compile(
    r"^(?:\d+\+)?[A-Za-z0-9][A-Za-z0-9._-]*@users\.noreply\.github\.com$"
)
DISALLOWED_IDENTITY_NAMES = {
    "Codex",
    "Claude",
    "Claude Code",
    "ChatGPT",
    "OpenAI",
    "github-actions[bot]",
} | LEGACY_PERSONAL_NAME_EXAMPLES
DISALLOWED_GITHUB_HOSTED_MERGE_AUTHOR_NAMES = {
    "Codex",
    "Claude",
    "Claude Code",
    "ChatGPT",
    "OpenAI",
    "github-actions[bot]",
}

LOG_FIELD_SEPARATOR = "\x1f"
LOG_RECORD_SEPARATOR = "\x1e"
IDENT_PATTERN = re.compile(r"^(?P<name>.+?) <(?P<email>[^<>]+)>(?: \d+ [+-]\d+)?$")


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


def _git_stdout(repo_root: Path, *args: str) -> str | None:
    completed = _run(["git", *args], cwd=repo_root)
    if not completed or completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _parse_ident(text: str) -> tuple[str, str] | None:
    match = IDENT_PATTERN.match(text.strip())
    if not match:
        return None
    return match.group("name"), match.group("email")


def _is_noreply_email(email: str) -> bool:
    return bool(NOREPLY_EMAIL_PATTERN.match(email))


def _is_disallowed_identity_name(name: str) -> bool:
    normalized = name.strip()
    return not normalized or normalized in DISALLOWED_IDENTITY_NAMES


def _is_disallowed_identity_email(email: str) -> bool:
    return email.strip() in LEGACY_PERSONAL_EMAILS


def _is_privacy_preserving_identity(name: str, email: str) -> bool:
    return (
        not _is_disallowed_identity_name(name)
        and _is_noreply_email(email)
        and not _is_disallowed_identity_email(email)
    )


def _is_allowed_history_identity(name: str, email: str) -> bool:
    if (name, email) == (GITHUB_NAME, GITHUB_EMAIL):
        return True
    if name == DEPENDABOT_NAME and email in DEPENDABOT_EMAILS:
        return True
    return _is_privacy_preserving_identity(name, email)


def _is_allowed_github_hosted_merge_author(name: str, email: str) -> bool:
    normalized = name.strip()
    return (
        bool(normalized)
        and normalized not in DISALLOWED_GITHUB_HOSTED_MERGE_AUTHOR_NAMES
        and _is_noreply_email(email)
    )


def _is_github_synthetic_merge_commit(
    *,
    author_name: str,
    author_email: str,
    committer_name: str,
    committer_email: str,
    parents_text: str,
    body: str,
) -> bool:
    if (committer_name, committer_email) != (GITHUB_NAME, GITHUB_EMAIL):
        return False
    if len(parents_text.split()) != 2:
        return False
    if not _is_allowed_history_identity(author_name, author_email):
        return False
    subject = next((line.strip() for line in body.splitlines() if line.strip()), "")
    return subject.startswith("Merge ")


def _is_github_hosted_squash_merge_commit(
    *,
    author_name: str,
    author_email: str,
    committer_name: str,
    committer_email: str,
    parents_text: str,
    body: str,
) -> bool:
    if (committer_name, committer_email) != (GITHUB_NAME, GITHUB_EMAIL):
        return False
    if len(parents_text.split()) not in {0, 1}:
        return False
    if not _is_allowed_github_hosted_merge_author(author_name, author_email):
        return False
    return True


def _iter_commit_records(repo_root: Path) -> list[tuple[str, str, str, str, str, str, str]]:
    completed = _run(
        [
            "git",
            "log",
            "--branches",
            "--tags",
            f"--format=%H{LOG_FIELD_SEPARATOR}%P{LOG_FIELD_SEPARATOR}%an{LOG_FIELD_SEPARATOR}%ae"
            f"{LOG_FIELD_SEPARATOR}%cn{LOG_FIELD_SEPARATOR}%ce{LOG_FIELD_SEPARATOR}%B"
            f"{LOG_RECORD_SEPARATOR}",
        ],
        cwd=repo_root,
    )
    if not completed:
        raise RuntimeError("Unable to run 'git log': git executable not found or not accessible")
    if completed.returncode not in (0, 128):
        stderr = completed.stderr.strip() if completed.stderr else ""
        message = f"'git log' failed with exit code {completed.returncode}"
        if stderr:
            message += f": {stderr}"
        raise RuntimeError(message)
    if completed.returncode == 128 or not completed.stdout.strip():
        return []

    records: list[tuple[str, str, str, str, str, str, str]] = []
    for raw_record in completed.stdout.split(LOG_RECORD_SEPARATOR):
        record = raw_record.strip()
        if not record:
            continue
        parts = record.split(LOG_FIELD_SEPARATOR, 6)
        if len(parts) != 7:
            continue
        records.append(tuple(parts))  # type: ignore[arg-type]
    return records


def collect_config_identity_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    local_name = _git_stdout(repo_root, "config", "--local", "--get", "user.name")
    local_email = _git_stdout(repo_root, "config", "--local", "--get", "user.email")

    if local_name is None or _is_disallowed_identity_name(local_name):
        errors.append(
            "repo-local git user.name must be a stable non-empty contributor name "
            f"(for example {CONFIG_NAME_EXAMPLE!r}), got {local_name!r}"
        )
    if local_email is None or not _is_noreply_email(local_email):
        errors.append(
            "repo-local git user.email must use a GitHub noreply address "
            f"(for example {CONFIG_EMAIL_EXAMPLE!r}), got {local_email!r}"
        )

    for label, variable in (
        ("author", "GIT_AUTHOR_IDENT"),
        ("committer", "GIT_COMMITTER_IDENT"),
    ):
        ident_text = _git_stdout(repo_root, "var", variable)
        if ident_text is None:
            errors.append(f"git var {variable} is unavailable")
            continue
        parsed = _parse_ident(ident_text)
        if not parsed:
            errors.append(f"unable to parse git var {variable}: {ident_text!r}")
            continue
        if not _is_privacy_preserving_identity(*parsed):
            errors.append(
                f"git var {variable} resolved to {parsed[0]!r} <{parsed[1]}>; "
                "expected a stable non-empty name plus a GitHub noreply email"
            )

    return errors


def collect_history_identity_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    try:
        records = _iter_commit_records(repo_root)
    except RuntimeError as exc:
        return [str(exc)]

    for (
        commit,
        parents_text,
        author_name,
        author_email,
        committer_name,
        committer_email,
        body,
    ) in records:
        if _is_github_synthetic_merge_commit(
            author_name=author_name,
            author_email=author_email,
            committer_name=committer_name,
            committer_email=committer_email,
            parents_text=parents_text,
            body=body,
        ):
            continue
        if _is_github_hosted_squash_merge_commit(
            author_name=author_name,
            author_email=author_email,
            committer_name=committer_name,
            committer_email=committer_email,
            parents_text=parents_text,
            body=body,
        ):
            continue
        if not _is_allowed_history_identity(author_name, author_email):
            errors.append(
                f"{commit}: author {author_name!r} <{author_email}> is not allowlisted"
            )
        if not _is_allowed_history_identity(committer_name, committer_email):
            errors.append(
                f"{commit}: committer {committer_name!r} <{committer_email}> is not allowlisted"
            )

        for line in body.splitlines():
            if not line.lower().startswith("co-authored-by:"):
                continue
            trailer_value = line.split(":", 1)[1].strip()
            parsed = _parse_ident(trailer_value)
            if not parsed:
                errors.append(f"{commit}: malformed Co-authored-by trailer: {line}")
                continue
            if not _is_allowed_history_identity(*parsed):
                errors.append(
                    f"{commit}: Co-authored-by trailer {parsed[0]!r} <{parsed[1]}> is not allowlisted"
                )

    return errors


def collect_identity_errors(repo_root: Path, *, mode: str = "all") -> list[str]:
    errors: list[str] = []

    if mode in {"all", "config"}:
        errors.extend(collect_config_identity_errors(repo_root))
    if mode in {"all", "history"}:
        errors.extend(collect_history_identity_errors(repo_root))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("all", "config", "history"),
        default="all",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    errors = collect_identity_errors(repo_root, mode=args.mode)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"commit identity check passed ({args.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
