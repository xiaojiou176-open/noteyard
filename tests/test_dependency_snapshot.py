from __future__ import annotations

import json
from pathlib import Path

import scripts.ci.submit_dependency_snapshot as snapshot_gate
from scripts.ci.submit_dependency_snapshot import InstalledPackage


def test_load_direct_dependency_scopes_marks_runtime_and_dev_groups(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "\n".join(
            [
                "[project]",
                'name = "notes-recover"',
                'dependencies = ["httpx>=0.28.1"]',
                "",
                "[project.optional-dependencies]",
                'dev = ["pytest", "pre-commit"]',
                'mcp = ["mcp>=1.26.0,<2"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scopes = snapshot_gate.load_direct_dependency_scopes(pyproject)

    assert scopes["httpx"] == "runtime"
    assert scopes["pytest"] == "development"
    assert scopes["pre-commit"] == "development"
    assert scopes["mcp"] == "runtime"


def test_build_snapshot_marks_direct_and_indirect_packages(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Dependency Snapshot")
    monkeypatch.setenv("GITHUB_JOB", "dependency-snapshot")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")

    snapshot = snapshot_gate.build_snapshot(
        repo_slug="owner/repo",
        project_name="notes-recover",
        packages=[
            InstalledPackage(name="httpx", version="0.28.1"),
            InstalledPackage(name="idna", version="3.11"),
            InstalledPackage(name="pytest", version="8.4.2"),
        ],
        direct_scopes={"httpx": "runtime", "pytest": "development"},
        sha="4b617593a4a3c92bf5c9117e40d5347c2ee446df",
        ref="refs/heads/main",
    )

    resolved = snapshot["manifests"][snapshot_gate.DEFAULT_MANIFEST_KEY]["resolved"]

    assert resolved["httpx"]["relationship"] == "direct"
    assert resolved["httpx"]["scope"] == "runtime"
    assert resolved["pytest"]["relationship"] == "direct"
    assert resolved["pytest"]["scope"] == "development"
    assert resolved["idna"]["relationship"] == "indirect"
    assert resolved["httpx"]["package_url"] == "pkg:pypi/httpx@0.28.1"


def test_resolve_sha_and_ref_prefers_pull_request_head(monkeypatch, tmp_path: Path) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps(
            {
                "pull_request": {
                    "head": {
                        "sha": "1234567890abcdef1234567890abcdef12345678",
                        "ref": "feature/dependency-proof",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_SHA", "deadbeef")
    monkeypatch.setenv("GITHUB_REF", "refs/pull/1/merge")

    sha, ref = snapshot_gate.resolve_sha_and_ref(tmp_path)

    assert sha == "1234567890abcdef1234567890abcdef12345678"
    assert ref == "refs/heads/feature/dependency-proof"


def test_resolve_sha_and_ref_falls_back_to_local_git(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.delenv("GITHUB_REF", raising=False)

    calls: list[tuple[str, ...]] = []

    def fake_check_output(command: list[str], cwd: Path, text: bool) -> str:
        calls.append(tuple(command))
        assert cwd == tmp_path
        assert text is True
        if command == ["git", "rev-parse", "HEAD"]:
            return "abcdef1234567890abcdef1234567890abcdef12\n"
        if command == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return "main\n"
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(snapshot_gate.subprocess, "check_output", fake_check_output)

    sha, ref = snapshot_gate.resolve_sha_and_ref(tmp_path)

    assert sha == "abcdef1234567890abcdef1234567890abcdef12"
    assert ref == "refs/heads/main"
    assert calls == [
        ("git", "rev-parse", "HEAD"),
        ("git", "rev-parse", "--abbrev-ref", "HEAD"),
    ]
