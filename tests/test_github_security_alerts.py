from __future__ import annotations

import subprocess
from pathlib import Path

import scripts.ci.check_github_security_alerts as alert_gate
from scripts.ci.check_github_security_alerts import collect_github_security_alert_errors


def test_github_security_alert_gate_rejects_open_alerts(monkeypatch, tmp_path: Path) -> None:
    def fake_gh_json(repo_root: Path, endpoint: str):  # type: ignore[no-untyped-def]
        if "secret-scanning" in endpoint:
            return [{"number": 1}]
        if "code-scanning" in endpoint:
            return [{"number": 2}]
        return []

    monkeypatch.setattr(alert_gate, "_gh_json", fake_gh_json)
    monkeypatch.setattr(alert_gate, "_git_remote_slug", lambda repo_root: "owner/repo")

    errors = collect_github_security_alert_errors(tmp_path)

    assert any("secret-scanning open alerts" in error for error in errors)
    assert any("code-scanning open alerts" in error for error in errors)


def test_github_security_alert_gate_rejects_missing_slug(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(alert_gate, "_git_remote_slug", lambda repo_root: None)

    errors = collect_github_security_alert_errors(tmp_path)

    assert errors == ["unable to detect canonical GitHub repository slug from origin remote"]


def test_github_security_alert_gate_passes_when_alerts_are_zero(monkeypatch, tmp_path: Path) -> None:
    def fake_gh_json(repo_root: Path, endpoint: str):  # type: ignore[no-untyped-def]
        return []

    monkeypatch.setattr(alert_gate, "_gh_json", fake_gh_json)
    monkeypatch.setattr(alert_gate, "_git_remote_slug", lambda repo_root: "owner/repo")

    assert collect_github_security_alert_errors(tmp_path) == []


def test_gh_json_retries_transient_failure(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    responses = [
        subprocess.CompletedProcess(
            args=["gh", "api", "/repos/owner/repo/code-scanning/alerts"],
            returncode=1,
            stdout="",
            stderr="temporary failure",
        ),
        subprocess.CompletedProcess(
            args=["gh", "api", "/repos/owner/repo/code-scanning/alerts"],
            returncode=0,
            stdout="[]",
            stderr="",
        ),
    ]

    def fake_run(args: list[str], *, cwd: Path):  # type: ignore[no-untyped-def]
        calls.append(args)
        return responses.pop(0)

    monkeypatch.setattr(alert_gate, "_run", fake_run)
    monkeypatch.setattr(alert_gate.time, "sleep", lambda _seconds: None)

    assert alert_gate._gh_json(tmp_path, "/repos/owner/repo/code-scanning/alerts") == []
    assert len(calls) == 2


def test_github_security_alert_gate_allows_secret_scanning_fallback_when_enabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_gh_json(repo_root: Path, endpoint: str):  # type: ignore[no-untyped-def]
        if endpoint == "/repos/owner/repo/secret-scanning/alerts?per_page=100":
            return None
        if endpoint == "/repos/owner/repo/code-scanning/alerts?state=open&per_page=100":
            return []
        if endpoint == "/repos/owner/repo":
            return {"security_and_analysis": {"secret_scanning": {"status": "enabled"}}}
        return []

    monkeypatch.setattr(alert_gate, "_gh_json", fake_gh_json)
    monkeypatch.setattr(alert_gate, "_git_remote_slug", lambda repo_root: "owner/repo")

    assert (
        collect_github_security_alert_errors(
            tmp_path,
            allow_secret_scanning_fallback=True,
        )
        == []
    )


def test_github_security_alert_gate_rejects_secret_scanning_fallback_when_not_enabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_gh_json(repo_root: Path, endpoint: str):  # type: ignore[no-untyped-def]
        if endpoint == "/repos/owner/repo/secret-scanning/alerts?per_page=100":
            return None
        if endpoint == "/repos/owner/repo/code-scanning/alerts?state=open&per_page=100":
            return []
        if endpoint == "/repos/owner/repo":
            return {"security_and_analysis": {"secret_scanning": {"status": "disabled"}}}
        return []

    monkeypatch.setattr(alert_gate, "_gh_json", fake_gh_json)
    monkeypatch.setattr(alert_gate, "_git_remote_slug", lambda repo_root: "owner/repo")

    errors = collect_github_security_alert_errors(
        tmp_path,
        allow_secret_scanning_fallback=True,
    )

    assert errors == [
        "unable to query GitHub secret-scanning alerts and secret scanning is not confirmed enabled"
    ]


def test_github_security_alert_gate_allows_secret_scanning_fallback_when_metadata_is_unavailable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_gh_json(repo_root: Path, endpoint: str):  # type: ignore[no-untyped-def]
        if endpoint == "/repos/owner/repo/secret-scanning/alerts?per_page=100":
            return None
        if endpoint == "/repos/owner/repo/code-scanning/alerts?state=open&per_page=100":
            return []
        if endpoint == "/repos/owner/repo":
            return None
        return []

    monkeypatch.setattr(alert_gate, "_gh_json", fake_gh_json)
    monkeypatch.setattr(alert_gate, "_git_remote_slug", lambda repo_root: "owner/repo")

    assert (
        collect_github_security_alert_errors(
            tmp_path,
            allow_secret_scanning_fallback=True,
        )
        == []
    )
