from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def _run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _candidate_pythons(repo_root: Path) -> list[str]:
    candidates: list[str] = []
    for candidate in (
        sys.executable,
        str(repo_root / ".venv" / "bin" / "python"),
        os.path.join(os.environ["pythonLocation"], "bin", "python")
        if os.environ.get("pythonLocation")
        else None,
        shutil.which("python3"),
        shutil.which("python"),
    ):
        if not candidate:
            continue
        candidate_path = Path(candidate)
        if candidate_path.is_absolute() and not candidate_path.exists():
            continue
        if candidate in candidates:
            continue
        candidates.append(candidate)
    return candidates


def _module_runner(repo_root: Path, module: str) -> str:
    candidates = _candidate_pythons(repo_root)
    for candidate in candidates:
        try:
            result = _run([candidate, "-m", module, "--help"], cwd=repo_root)
        except OSError:
            continue
        if result.returncode == 0:
            return candidate
    tried = ", ".join(candidates) if candidates else "no candidate interpreters found"
    raise RuntimeError(
        f"Could not find a Python interpreter with `{module}` installed. Tried: {tried}"
    )


def _load_pyproject(repo_root: Path) -> dict[str, object]:
    with (repo_root / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def _load_server_json(repo_root: Path) -> dict[str, object]:
    return json.loads((repo_root / "server.json").read_text(encoding="utf-8"))


def collect_publish_readiness_errors(repo_root: Path) -> list[str]:
    pyproject = _load_pyproject(repo_root)
    server_payload = _load_server_json(repo_root)

    errors: list[str] = []

    project = pyproject.get("project")
    if not isinstance(project, dict):
        return ["pyproject.toml is missing [project] metadata"]

    project_name = project.get("name")
    project_version = project.get("version")
    if not isinstance(project_name, str) or not project_name:
        errors.append("pyproject.toml is missing project.name")
    if not isinstance(project_version, str) or not project_version:
        errors.append("pyproject.toml is missing project.version")

    packages = server_payload.get("packages")
    if not isinstance(packages, list) or not packages:
        errors.append("server.json is missing packages[]")
        return errors

    package = packages[0]
    if not isinstance(package, dict):
        errors.append("server.json packages[0] is not an object")
        return errors

    if server_payload.get("name") != "io.github.xiaojiou176-open/notes-recover-mcp":
        errors.append("server.json name drifted from the canonical MCP identifier")

    repository = server_payload.get("repository")
    if not isinstance(repository, dict):
        errors.append("server.json is missing repository metadata")
    else:
        if repository.get("url") != "https://github.com/xiaojiou176-open/notes-recover":
            errors.append("server.json repository.url must point at the canonical GitHub repository")
        if repository.get("source") != "github":
            errors.append("server.json repository.source must be github")

    if package.get("registryType") != "pypi":
        errors.append("server.json packages[0].registryType must stay pypi for the current MCP publication story")
    if package.get("identifier") != project_name:
        errors.append("server.json package identifier must match pyproject project.name")
    if package.get("version") != project_version:
        errors.append("server.json package version must match pyproject project.version")
    if server_payload.get("version") != project_version:
        errors.append("server.json top-level version must match pyproject project.version")

    transport = package.get("transport")
    if not isinstance(transport, dict) or transport.get("type") != "stdio":
        errors.append("server.json transport must stay stdio for the current MCP distribution contract")

    return errors


def build_and_check(repo_root: Path) -> dict[str, object]:
    errors = collect_publish_readiness_errors(repo_root)
    if errors:
        return {"ok": False, "errors": errors}

    try:
        build_python = _module_runner(repo_root, "build")
        twine_python = _module_runner(repo_root, "twine")
    except RuntimeError as exc:
        return {"ok": False, "errors": [str(exc)]}

    with tempfile.TemporaryDirectory(prefix="notes-recover-pypi-dist-") as tmpdir:
        out_dir = Path(tmpdir)
        build_result = _run(
            [build_python, "-m", "build", "--sdist", "--wheel", "--outdir", str(out_dir)],
            cwd=repo_root,
        )
        if build_result.returncode != 0:
            return {
                "ok": False,
                "errors": ["python -m build failed"],
                "build_python": build_python,
                "build_stdout": build_result.stdout,
                "build_stderr": build_result.stderr,
            }

        artifacts = sorted(path.name for path in out_dir.iterdir() if path.is_file())
        twine_result = _run(
            [twine_python, "-m", "twine", "check", *[str(path) for path in sorted(out_dir.iterdir())]],
            cwd=repo_root,
        )
        if twine_result.returncode != 0:
            return {
                "ok": False,
                "errors": ["twine check failed"],
                "artifacts": artifacts,
                "twine_python": twine_python,
                "twine_stdout": twine_result.stdout,
                "twine_stderr": twine_result.stderr,
            }

        return {
            "ok": True,
            "artifacts": artifacts,
            "build_python": build_python,
            "twine_python": twine_python,
            "build_stdout": build_result.stdout,
            "twine_stdout": twine_result.stdout,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Only verify pyproject/server.json alignment without building artifacts",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    if args.metadata_only:
        errors = collect_publish_readiness_errors(repo_root)
        payload = {"ok": not errors, "errors": errors}
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return 0 if not errors else 1

    payload = build_and_check(repo_root)
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
