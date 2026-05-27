from __future__ import annotations

from pathlib import Path

from scripts.release.check_pypi_publish_readiness import (
    _module_runner,
    collect_publish_readiness_errors,
)


def test_collect_publish_readiness_errors_passes_for_repo_root() -> None:
    errors = collect_publish_readiness_errors(Path.cwd())
    assert errors == []


def test_publish_readiness_is_wired_into_hosted_guardrails() -> None:
    repo_root = Path.cwd()
    precommit_text = (repo_root / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    workflow_text = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "check_pypi_publish_readiness.py" not in precommit_text
    assert "PyPI publish readiness pre-push gate" not in precommit_text
    assert "distribution-readiness:" in workflow_text
    assert "Check distribution metadata and build readiness" in workflow_text
    assert "check_pypi_publish_readiness.py" in workflow_text


def test_module_runner_prefers_repo_venv_fallback(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path
    venv_python = repo_root / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")

    calls: list[tuple[str, ...]] = []

    class _Result:
        def __init__(self, returncode: int):
            self.returncode = returncode
            self.stdout = ""
            self.stderr = ""

    def fake_run(args: list[str], *, cwd: Path):
        calls.append(tuple(args))
        if args[0] == "/usr/bin/python3":
            return _Result(1)
        if args[0] == str(venv_python):
            return _Result(0)
        return _Result(1)

    monkeypatch.setattr(
        "scripts.release.check_pypi_publish_readiness._candidate_pythons",
        lambda _repo_root: ["/usr/bin/python3", str(venv_python)],
    )
    monkeypatch.setattr(
        "scripts.release.check_pypi_publish_readiness._run",
        fake_run,
    )

    assert _module_runner(repo_root, "build") == str(venv_python)
    assert calls == [
        ("/usr/bin/python3", "-m", "build", "--help"),
        (str(venv_python), "-m", "build", "--help"),
    ]
