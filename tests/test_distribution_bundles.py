from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from scripts.release.build_distribution_bundles import build_distribution_bundles


def test_distribution_artifacts_exist() -> None:
    repo_root = Path.cwd()

    server_payload = json.loads((repo_root / "server.json").read_text(encoding="utf-8"))
    marketplace_payload = json.loads(
        (repo_root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    distribution_text = (repo_root / "DISTRIBUTION.md").read_text(encoding="utf-8")

    assert server_payload["name"] == "io.github.xiaojiou176-open/notestorelab-mcp"
    assert server_payload["repository"]["url"] == "https://github.com/xiaojiou176-open/noteyard"
    assert server_payload["repository"]["source"] == "github"
    assert server_payload["packages"][0]["identifier"] == "noteyard"
    assert marketplace_payload["name"] == "notestorelab-plugins"
    assert marketplace_payload["owner"]["email"].endswith("@users.noreply.github.com")
    assert marketplace_payload["plugins"][0]["name"] == "notestorelab-claude-plugin"
    assert marketplace_payload["plugins"][0]["author"]["email"] == marketplace_payload["owner"]["email"]
    assert marketplace_payload["plugins"][0]["source"] == "./plugins/notestorelab-claude-plugin"
    assert "intended PyPI package identifier and version" in distribution_text
    assert (
        "the intake is submitted on [`cline/mcp-marketplace#1324`]"
        in distribution_text
    )
    assert (
        '"the Cline MCP Marketplace intake is submitted and review-pending on '
        '`cline/mcp-marketplace#1324`"'
        in distribution_text
    )
    assert (
        '"Cline MCP Marketplace is listed live" without fresh marketplace read-back'
        in distribution_text
    )
    assert '"MCP Registry submission completed"' in distribution_text

    assert (repo_root / "plugins" / "notestorelab-codex-plugin" / ".codex-plugin" / "plugin.json").exists()
    assert (repo_root / "plugins" / "notestorelab-codex-plugin" / ".mcp.json").exists()
    assert (repo_root / "plugins" / "notestorelab-claude-plugin" / ".claude-plugin" / "plugin.json").exists()
    assert (repo_root / "plugins" / "notestorelab-claude-plugin" / ".mcp.json").exists()
    assert (repo_root / "plugins" / "notestorelab-openclaw-bundle" / ".claude-plugin" / "plugin.json").exists()


def test_build_distribution_bundles(tmp_path: Path) -> None:
    result = build_distribution_bundles(tmp_path)

    manifest_path = Path(result["manifest"])
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle_keys = {item["key"] for item in manifest["bundles"]}
    assert bundle_keys == {"codex", "claude", "openclaw"}

    expected_entries = {
        "codex": {
            "notestorelab-codex-plugin/.codex-plugin/plugin.json",
            "notestorelab-codex-plugin/.mcp.json",
            "notestorelab-codex-plugin/bin/notestorelab-mcp",
            "notestorelab-codex-plugin/skills/notestorelab-case-review/SKILL.md",
        },
        "claude": {
            "notestorelab-claude-plugin/.claude-plugin/plugin.json",
            "notestorelab-claude-plugin/.mcp.json",
            "notestorelab-claude-plugin/bin/notestorelab-mcp",
        },
        "openclaw": {
            "notestorelab-openclaw-bundle/.claude-plugin/plugin.json",
            "notestorelab-openclaw-bundle/.mcp.json",
            "notestorelab-openclaw-bundle/bin/notestorelab-mcp",
        },
    }

    for item in manifest["bundles"]:
        archive_path = Path(item["archive"])
        assert archive_path.exists()
        with ZipFile(archive_path, "r") as bundle:
            names = set(bundle.namelist())
        assert expected_entries[item["key"]].issubset(names)
