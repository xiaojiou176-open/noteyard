from __future__ import annotations

from pathlib import Path

from scripts.ci.check_sensitive_surface import collect_sensitive_surface_errors


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_sensitive_surface_allows_repo_guardrail_identity_and_synthetic_fixture(tmp_path: Path) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        'git config --local user.email "repo-guardrail@users.noreply.github.com"\n',
    )
    _write(tmp_path / ".env.example", "NOTES_CASE_HMAC_KEY=\n")
    _write(tmp_path / "tests" / "data" / "icloud_min.sqlite", "synthetic fixture\n")

    errors = collect_sensitive_surface_errors(
        tmp_path,
        tracked_files=[
            ".env.example",
            ".github/workflows/ci.yml",
            "tests/data/icloud_min.sqlite",
        ],
    )

    assert errors == []


def test_sensitive_surface_allows_canonical_owner_noreply_in_marketplace_metadata(tmp_path: Path) -> None:
    owner_email = "xiaojiou176" + "@users.noreply.github.com"
    _write(
        tmp_path / ".claude-plugin" / "marketplace.json",
        "\n".join(
            [
                "{",
                f'  "owner": {{"email": "{owner_email}"}},',
                f'  "plugins": [{{"author": {{"email": "{owner_email}"}}}}]',
                "}",
            ]
        ),
    )

    errors = collect_sensitive_surface_errors(
        tmp_path,
        tracked_files=[".claude-plugin/marketplace.json"],
    )

    assert errors == []


def test_sensitive_surface_rejects_legacy_identity_and_github_noreply_email(tmp_path: Path) -> None:
    legacy_name = "Yifeng" + "[Terry]" + " Yu"
    legacy_email = "125581657+" + "xiaojiou176" + "@users.noreply.github.com"
    _write(
        tmp_path / "CONTRIBUTING.md",
        f"{legacy_name}\n{legacy_email}\n",
    )

    errors = collect_sensitive_surface_errors(tmp_path, tracked_files=["CONTRIBUTING.md"])

    assert any("legacy maintainer identity" in error for error in errors)
    assert any("non-allowlisted GitHub noreply email" in error for error in errors)


def test_sensitive_surface_rejects_absolute_path_like_strings(tmp_path: Path) -> None:
    users_prefix = "/" + "Users" + "/"
    _write(tmp_path / "README.md", users_prefix + "alice/private/project\n")

    errors = collect_sensitive_surface_errors(tmp_path, tracked_files=["README.md"])

    assert any("absolute path-like string" in error for error in errors)


def test_sensitive_surface_rejects_tracked_sensitive_artifact_paths(tmp_path: Path) -> None:
    _write(tmp_path / "logs" / "app.log", "not important\n")

    errors = collect_sensitive_surface_errors(tmp_path, tracked_files=["logs/app.log"])

    assert any("tracked sensitive artifact path" in error for error in errors)


def test_sensitive_surface_rejects_tracked_sqlite_outside_allowlist(tmp_path: Path) -> None:
    _write(tmp_path / "fixtures" / "prod.sqlite", "db\n")

    errors = collect_sensitive_surface_errors(tmp_path, tracked_files=["fixtures/prod.sqlite"])

    assert any("tracked sensitive artifact path" in error for error in errors)
