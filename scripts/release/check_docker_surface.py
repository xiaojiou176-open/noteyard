from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path


REPO_URL = "https://github.com/xiaojiou176-open/noteyard"
SERVER_NAME = "io.github.xiaojiou176-open/notestorelab-mcp"
IMAGE_BASE = "ghcr.io/xiaojiou176-open/noteyard"


def _run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _project_version(repo_root: Path) -> str:
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(pyproject["project"]["version"])


def collect_docker_surface_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []
    project_version = _project_version(repo_root)
    local_image_tag = f"notestorelab:{project_version}"

    dockerfile = repo_root / "Dockerfile"
    dockerignore = repo_root / ".dockerignore"
    if not dockerfile.exists():
        return ["missing Dockerfile"]
    if not dockerignore.exists():
        errors.append("missing .dockerignore")

    docker_text = dockerfile.read_text(encoding="utf-8")
    if "FROM python:3.11-slim" not in docker_text:
        errors.append("Dockerfile must stay on python:3.11-slim for the current container story")
    if f'LABEL io.modelcontextprotocol.server.name="{SERVER_NAME}"' not in docker_text:
        errors.append("Dockerfile must set io.modelcontextprotocol.server.name for OCI readiness")
    if 'python -m pip install ".[mcp]"' not in docker_text:
        errors.append("Dockerfile must install the package with the mcp extra")
    if 'CMD ["notes-recovery", "--help"]' not in docker_text:
        errors.append("Dockerfile must default to notes-recovery --help")

    readme_text = (repo_root / "README.md").read_text(encoding="utf-8")
    integrations_text = (repo_root / "INTEGRATIONS.md").read_text(encoding="utf-8")
    distribution_text = (repo_root / "DISTRIBUTION.md").read_text(encoding="utf-8")
    if f"docker build -t {local_image_tag} ." not in readme_text:
        errors.append("README.md must include the canonical docker build command")
    if f"docker run --rm {local_image_tag} notes-recovery demo" not in readme_text:
        errors.append("README.md must include the canonical docker demo command")
    if "--entrypoint notes-recovery-mcp" not in integrations_text:
        errors.append("INTEGRATIONS.md must show the MCP container entrypoint override")
    if "Docker-ready local container surface shipped" not in distribution_text:
        errors.append("DISTRIBUTION.md must describe the Docker-ready local container surface")
    if IMAGE_BASE not in distribution_text:
        errors.append("DISTRIBUTION.md must describe the canonical GHCR image target")
    if "not a hosted service" not in readme_text:
        errors.append("README.md must keep the container path out of hosted-service language")

    return errors


def build_and_smoke(repo_root: Path) -> dict[str, object]:
    errors = collect_docker_surface_errors(repo_root)
    if errors:
        return {"ok": False, "errors": errors}

    if shutil.which("docker") is None:
        return {"ok": False, "errors": ["docker is not installed"]}  # pragma: no cover

    with tempfile.TemporaryDirectory(prefix="notestorelab-docker-smoke-"):
        image_tag = f"notestorelab-smoke:{Path(repo_root).name}"
        build_result = _run(["docker", "build", "-t", image_tag, "."], cwd=repo_root)
        if build_result.returncode != 0:
            return {
                "ok": False,
                "errors": ["docker build failed"],
                "build_stdout": build_result.stdout,
                "build_stderr": build_result.stderr,
            }

        smoke_results: list[dict[str, object]] = []
        for command in (
            ["docker", "run", "--rm", image_tag, "notes-recovery", "--help"],
            ["docker", "run", "--rm", image_tag, "notes-recovery-mcp", "--help"],
            ["docker", "run", "--rm", image_tag, "notes-recovery", "demo"],
        ):
            result = _run(command, cwd=repo_root)
            smoke_results.append(
                {
                    "command": " ".join(command),
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
            if result.returncode != 0:
                return {
                    "ok": False,
                    "errors": ["docker smoke failed"],
                    "smoke_results": smoke_results,
                }

        return {
            "ok": True,
            "image_tag": image_tag,
            "smoke_results": smoke_results,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Only verify Dockerfile/doc alignment without building the image",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    if args.metadata_only:
        errors = collect_docker_surface_errors(repo_root)
        payload = {"ok": not errors, "errors": errors}
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return 0 if not errors else 1

    payload = build_and_smoke(repo_root)
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
