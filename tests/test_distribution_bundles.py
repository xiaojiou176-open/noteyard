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

    assert server_payload["name"] == "io.github.xiaojiou176-open/notes-recover-mcp"
    assert server_payload["repository"]["url"] == "https://github.com/xiaojiou176-open/notes-recover"
    assert server_payload["repository"]["source"] == "github"
    assert server_payload["packages"][0]["identifier"] == "notes-recover"
    assert marketplace_payload["name"] == "notes-recover-plugins"
    assert marketplace_payload["owner"]["email"].endswith("@users.noreply.github.com")
    assert marketplace_payload["plugins"][0]["name"] == "notes-recover-claude-plugin"
    assert marketplace_payload["plugins"][0]["author"]["email"] == marketplace_payload["owner"]["email"]
    assert marketplace_payload["plugins"][0]["source"] == "./plugins/notes-recover-claude-plugin"
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

    assert (repo_root / "plugins" / "notes-recover-codex-plugin" / ".codex-plugin" / "plugin.json").exists()
    assert (repo_root / "plugins" / "notes-recover-codex-plugin" / ".mcp.json").exists()
    assert (repo_root / "plugins" / "notes-recover-claude-plugin" / ".claude-plugin" / "plugin.json").exists()
    assert (repo_root / "plugins" / "notes-recover-claude-plugin" / ".mcp.json").exists()
    assert (repo_root / "plugins" / "notes-recover-openclaw-bundle" / ".claude-plugin" / "plugin.json").exists()


def test_build_distribution_bundles(tmp_path: Path) -> None:
    result = build_distribution_bundles(tmp_path)

    manifest_path = Path(result["manifest"])
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle_keys = {item["key"] for item in manifest["bundles"]}
    assert bundle_keys == {"codex", "claude", "openclaw"}

    expected_entries = {
        "codex": {
            "notes-recover-codex-plugin/.codex-plugin/plugin.json",
            "notes-recover-codex-plugin/.mcp.json",
            "notes-recover-codex-plugin/bin/notes-recover-mcp",
            "notes-recover-codex-plugin/skills/notes-recover-case-review/SKILL.md",
        },
        "claude": {
            "notes-recover-claude-plugin/.claude-plugin/plugin.json",
            "notes-recover-claude-plugin/.mcp.json",
            "notes-recover-claude-plugin/bin/notes-recover-mcp",
        },
        "openclaw": {
            "notes-recover-openclaw-bundle/.claude-plugin/plugin.json",
            "notes-recover-openclaw-bundle/.mcp.json",
            "notes-recover-openclaw-bundle/bin/notes-recover-mcp",
        },
    }

    for item in manifest["bundles"]:
        archive_path = Path(item["archive"])
        assert archive_path.exists()
        with ZipFile(archive_path, "r") as bundle:
            names = set(bundle.namelist())
        assert expected_entries[item["key"]].issubset(names)
