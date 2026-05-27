from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__ in {None, ""}:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))

if Path(__file__).resolve().suffix == ".py":
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore


CANONICAL_SKILL_DIR = Path("skills/noteyard-case-review")
DERIVED_SKILL_PATHS = (
    Path("plugins/noteyard-codex-plugin/skills/noteyard-case-review/SKILL.md"),
    Path("starter-bundles/codex/plugins/noteyard/skills/noteyard-mcp/SKILL.md"),
    Path("starter-bundles/claude-code/plugins/noteyard/skills/noteyard-mcp/SKILL.md"),
    Path("plugins/noteyard-openclaw-bundle/workspace/skills/noteyard/SKILL.md"),
    Path("starter-bundles/openclaw/workspace/skills/noteyard/SKILL.md"),
)
REPO_URL = "https://github.com/xiaojiou176-open/noteyard"
CANONICAL_NAME = "noteyard-case-review"
PUBLIC_SKILL_DIR = Path("public-skills/noteyard-case-review")
PUBLIC_SKILL_SEMVER = "1.0.2"
LEGACY_PUBLIC_REFERENCE_FILES = (
    PUBLIC_SKILL_DIR / "references" / "install-and-mcp.md",
    PUBLIC_SKILL_DIR / "references" / "usage-and-proof.md",
)
PUBLIC_SKILL_DEMO_PATH = PUBLIC_SKILL_DIR / "references" / "DEMO.md"


def _load_pyproject(repo_root: Path) -> dict[str, object]:
    with (repo_root / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    _, remainder = text.split("---\n", 1)
    frontmatter_text, _, _ = remainder.partition("\n---\n")
    payload: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        payload[key.strip()] = raw_value.strip()
    return payload


def _manifest_scalar(text: str, key: str) -> str | None:
    prefix = f"{key}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def _manifest_has_section(text: str, key: str) -> bool:
    prefix = f"{key}:"
    return any(line.startswith(prefix) for line in text.splitlines())


def collect_skill_publish_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    canonical_skill = repo_root / CANONICAL_SKILL_DIR / "SKILL.md"
    canonical_manifest = repo_root / CANONICAL_SKILL_DIR / "manifest.yaml"

    if not canonical_skill.exists():
        return [f"missing canonical skill: {canonical_skill.relative_to(repo_root)}"]
    if not canonical_manifest.exists():
        return [f"missing canonical skill manifest: {canonical_manifest.relative_to(repo_root)}"]

    canonical_text = canonical_skill.read_text(encoding="utf-8")
    frontmatter = _frontmatter(canonical_text)
    if frontmatter.get("name") != CANONICAL_NAME:
        errors.append("canonical SKILL.md frontmatter name must stay noteyard-case-review")
    if not frontmatter.get("description"):
        errors.append("canonical SKILL.md frontmatter is missing description")

    for rel_path in DERIVED_SKILL_PATHS:
        derived_path = repo_root / rel_path
        if not derived_path.exists():
            errors.append(f"missing derived skill copy: {rel_path}")
            continue
        if derived_path.read_text(encoding="utf-8") != canonical_text:
            errors.append(f"derived skill copy drifted from canonical skill: {rel_path}")

    manifest_text = canonical_manifest.read_text(encoding="utf-8")
    for key in (
        "name",
        "description",
        "version",
        "homepage",
        "repository",
        "license",
        "entrypoint",
        "capabilities",
        "scope",
        "runtime",
        "install_guidance",
    ):
        if not _manifest_has_section(manifest_text, key):
            errors.append(f"manifest.yaml is missing required field: {key}")

    if _manifest_scalar(manifest_text, "name") != CANONICAL_NAME:
        errors.append("manifest.yaml name must stay noteyard-case-review")

    pyproject = _load_pyproject(repo_root)
    project = pyproject.get("project")
    version = project.get("version") if isinstance(project, dict) else None
    if _manifest_scalar(manifest_text, "version") != version:
        errors.append("manifest.yaml version must match pyproject.toml project.version")

    if _manifest_scalar(manifest_text, "homepage") != REPO_URL:
        errors.append("manifest.yaml homepage must point at the canonical GitHub repository")
    if _manifest_scalar(manifest_text, "repository") != REPO_URL:
        errors.append("manifest.yaml repository must point at the canonical GitHub repository")
    if _manifest_scalar(manifest_text, "license") != "MIT":
        errors.append("manifest.yaml license must stay MIT")
    if _manifest_scalar(manifest_text, "entrypoint") != "./SKILL.md":
        errors.append("manifest.yaml entrypoint must stay ./SKILL.md")

    public_skill_dir = repo_root / PUBLIC_SKILL_DIR
    public_skill_manifest = public_skill_dir / "manifest.yaml"
    public_skill_readme = public_skill_dir / "README.md"
    public_skill_demo = repo_root / PUBLIC_SKILL_DEMO_PATH
    public_skill_root_readme = repo_root / "public-skills" / "README.md"
    if not public_skill_dir.exists():
        errors.append(f"missing public skill directory: {PUBLIC_SKILL_DIR}")
    if not public_skill_manifest.exists():
        errors.append(f"missing public skill manifest: {public_skill_manifest.relative_to(repo_root)}")
    if not public_skill_readme.exists():
        errors.append(f"missing public skill README: {public_skill_readme.relative_to(repo_root)}")
    if not public_skill_demo.exists():
        errors.append(f"missing public skill demo reference: {public_skill_demo.relative_to(repo_root)}")
    if not public_skill_root_readme.exists():
        errors.append("missing public-skills/README.md")
    if public_skill_manifest.exists():
        public_manifest_text = public_skill_manifest.read_text(encoding="utf-8")
        for token in (
            "schema_version: 1",
            "artifact: public-skill-listing-manifest",
            "name: noteyard-case-review",
            "version: 1.0.2",
            "display_name: Noteyard Case Review",
            "package_shape: skill-folder",
            "clawhub:",
            "openhands-extensions:",
            "status: listed-live",
            "live_read_back: https://clawhub.ai/xiaojiou176/noteyard-case-review",
            "status: submission-done-platform-not-accepted-yet",
            "review_state: changes-requested",
            "submit_via: clawhub publish .",
            "submit_via: submit this folder as skills/noteyard-case-review/ in OpenHands/extensions",
            "canonical_repo_version: 0.1.0.post1",
            "official_listing_state: clawhub-listed-live-openhands-submission-done",
            "confirmed_live:",
            "ClawHub public skill listing is live at https://clawhub.ai/xiaojiou176/noteyard-case-review",
            "references/README.md",
            "references/INSTALL.md",
            "references/OPENHANDS_MCP_CONFIG.json",
            "references/OPENCLAW_MCP_CONFIG.json",
            "references/CAPABILITIES.md",
            "references/DEMO.md",
            "references/TROUBLESHOOTING.md",
        ):
            if token not in public_manifest_text:
                errors.append(f"public skill manifest is missing required token: {token}")
    if public_skill_readme.exists():
        public_readme_text = public_skill_readme.read_text(encoding="utf-8")
        for token in (
            "OpenHands/extensions-friendly",
            "ClawHub-style",
            "skills/noteyard-case-review/SKILL.md",
            "no official OpenHands/extensions listing without fresh PR/read-back",
            "Today the secondary ClawHub packet listing is live",
            "OpenHands/extensions submission still sits in a changes-requested review state",
            "What this skill teaches an agent",
            "Primary reviewer route:",
            "Use cases: https://github.com/xiaojiou176-open/noteyard/blob/main/USE_CASES.md",
            "Builder / raw-source references after the route above:",
            "Demo / proof links",
        ):
            if token not in public_readme_text:
                errors.append(f"public skill README is missing required token: {token}")
        for token in (
            "no live ClawHub listing without fresh host-side read-back",
        ):
            if token in public_readme_text:
                errors.append(f"public skill README still contains stale ClawHub wording: {token}")
    if public_skill_demo.exists():
        public_demo_text = public_skill_demo.read_text(encoding="utf-8")
        for token in (
            "Primary reviewer route:",
            "Landing page: https://xiaojiou176-open.github.io/noteyard/",
            "Public proof page: https://xiaojiou176-open.github.io/noteyard/proof.html",
            "Use cases: https://github.com/xiaojiou176-open/noteyard/blob/main/USE_CASES.md",
            "Builder / raw-source references after the route above:",
            "the secondary ClawHub packet listing is live",
            "submission-done plus changes-requested",
        ):
            if token not in public_demo_text:
                errors.append(f"public skill demo reference is missing required token: {token}")
        if "https://github.com/xiaojiou176-open/noteyard/blob/main/proof.html" in public_demo_text:
            errors.append(
                "public skill demo reference still points first-hop proof at a blob page"
            )
    if public_skill_root_readme.exists():
        public_skill_root_text = public_skill_root_readme.read_text(encoding="utf-8")
        for token in (
            "OpenHands/extensions-friendly public skill folder",
            "ClawHub-style manifest with semver-ready listing metadata",
            "today the secondary ClawHub public-skill listing is already live",
        ):
            if token not in public_skill_root_text:
                errors.append(f"public-skills/README.md is missing required token: {token}")
        for token in (
            "proof of a live listing on OpenHands/extensions, ClawHub, Glama, or Docker",
            "no live ClawHub listing today",
        ):
            if token in public_skill_root_text:
                errors.append(f"public-skills/README.md still contains stale listing wording: {token}")
    for legacy_ref in LEGACY_PUBLIC_REFERENCE_FILES:
        if (repo_root / legacy_ref).exists():
            errors.append(f"legacy public skill reference should be removed: {legacy_ref}")

    codex_plugin_payload = _load_json(
        repo_root / "plugins/noteyard-codex-plugin/.codex-plugin/plugin.json"
    )
    if codex_plugin_payload.get("version") != version:
        errors.append("Codex plugin version must match pyproject.toml project.version")
    if codex_plugin_payload.get("homepage") != REPO_URL:
        errors.append("Codex plugin homepage must match the canonical GitHub repository")
    if codex_plugin_payload.get("repository") != REPO_URL:
        errors.append("Codex plugin repository must match the canonical GitHub repository")
    if codex_plugin_payload.get("license") != "MIT":
        errors.append("Codex plugin license must stay MIT")

    marketplace_payload = _load_json(repo_root / ".claude-plugin/marketplace.json")
    plugins = marketplace_payload.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append(".claude-plugin/marketplace.json is missing plugins[]")
    else:
        first_plugin = plugins[0]
        if not isinstance(first_plugin, dict) or first_plugin.get("version") != version:
            errors.append("Claude marketplace plugin version must match pyproject.toml project.version")

    readme_text = (repo_root / "README.md").read_text(encoding="utf-8")
    distribution_text = (repo_root / "DISTRIBUTION.md").read_text(encoding="utf-8")
    integrations_text = (repo_root / "INTEGRATIONS.md").read_text(encoding="utf-8")
    contributing_text = (repo_root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    llms_text = (repo_root / "llms.txt").read_text(encoding="utf-8")
    ecosystem_text = (repo_root / "ECOSYSTEM.md").read_text(encoding="utf-8")
    if "skills/noteyard-case-review/" not in readme_text:
        errors.append("README.md must mention the canonical independent skill surface")
    if "public-skills/noteyard-case-review/" not in readme_text:
        errors.append("README.md must mention the OpenHands/ClawHub-facing public skill folder")
    if "independent skill surface" not in distribution_text:
        errors.append("DISTRIBUTION.md must describe the independent skill surface truthfully")
    if "OpenHands/extensions" not in distribution_text:
        errors.append("DISTRIBUTION.md must describe the OpenHands/extensions listing boundary")
    if "canonical independent skill surface" not in integrations_text:
        errors.append("INTEGRATIONS.md must describe the canonical independent skill surface")
    if "OpenHands/extensions-friendly public skill folder" not in integrations_text:
        errors.append("INTEGRATIONS.md must describe the OpenHands-facing public skill folder")
    for forbidden_token in (
        "Fresh PyPI read-back now confirms a live package",
        "active official MCP Registry listing",
        "The canonical live-image target is now verified at",
    ):
        if forbidden_token in integrations_text:
            errors.append(f"INTEGRATIONS.md should not reuse stale live-claim wording: {forbidden_token}")
        if forbidden_token in contributing_text:
            errors.append(f"CONTRIBUTING.md should not reuse stale live-claim wording: {forbidden_token}")
        if forbidden_token in llms_text:
            errors.append(f"llms.txt should not reuse stale live-claim wording: {forbidden_token}")
    if "OpenHands/extensions-ready public skill folder" not in ecosystem_text:
        errors.append("ECOSYSTEM.md must describe the OpenHands-facing public skill lane")
    for rel_path, text in (
        ("README.md", readme_text),
        ("DISTRIBUTION.md", distribution_text),
        ("INTEGRATIONS.md", integrations_text),
        ("llms.txt", llms_text),
        ("ECOSYSTEM.md", ecosystem_text),
    ):
        for token in (
            "no live ClawHub/OpenHands/extensions/Glama/Docker catalog listing language in Wave 1",
            "do not claim live ClawHub or official OpenClaw listing",
            "Treat ClawHub publication as a later manual external step",
            "do not claim a live ClawHub listing yet",
            "there is no live ClawHub listing claim yet",
            "no live ClawHub listing today",
        ):
            if token in text:
                errors.append(f"{rel_path} still contains stale ClawHub or OpenHands wording: {token}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    errors = collect_skill_publish_errors(repo_root)
    payload = {"ok": not errors, "errors": errors}
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
