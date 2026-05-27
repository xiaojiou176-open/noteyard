from __future__ import annotations

import argparse
import json
from pathlib import Path


GLAMA_SCHEMA = "https://glama.ai/mcp/schemas/server.json"
GLAMA_MAINTAINER = "xiaojiou176"
IMAGE_BASE = "ghcr.io/xiaojiou176-open/noteyard"


def collect_glama_surface_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    glama_json = repo_root / "glama.json"
    if not glama_json.exists():
        return ["missing glama.json"]

    payload = json.loads(glama_json.read_text(encoding="utf-8"))
    if payload.get("$schema") != GLAMA_SCHEMA:
        errors.append("glama.json must keep the official Glama schema URL")
    maintainers = payload.get("maintainers")
    if not isinstance(maintainers, list) or GLAMA_MAINTAINER not in maintainers:
        errors.append("glama.json must list xiaojiou176 as a maintainer")

    if not (repo_root / "Dockerfile").exists():
        errors.append("Glama surface requires a Dockerfile")

    readme_text = (repo_root / "README.md").read_text(encoding="utf-8")
    distribution_text = (repo_root / "DISTRIBUTION.md").read_text(encoding="utf-8")
    integrations_text = (repo_root / "INTEGRATIONS.md").read_text(encoding="utf-8")

    for token in (
        "glama.json",
        "OpenHands/extensions-friendly public skill folder",
        IMAGE_BASE,
    ):
        if token not in readme_text:
            errors.append(f"README.md is missing Glama surface token: {token}")

    for token in (
        "Glama",
        "glama.json",
        "Do not claim a live Glama listing",
        IMAGE_BASE,
    ):
        if token not in distribution_text:
            errors.append(f"DISTRIBUTION.md is missing Glama surface token: {token}")

    for token in (
        "Glama",
        "glama.json",
        IMAGE_BASE,
    ):
        if token not in integrations_text:
            errors.append(f"INTEGRATIONS.md is missing Glama surface token: {token}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    errors = collect_glama_surface_errors(repo_root)
    payload = {"ok": not errors, "errors": errors}
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
