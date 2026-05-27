from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from scripts.release.build_starter_bundles_bundle import build_bundle


def test_build_starter_bundles_bundle(tmp_path: Path) -> None:
    out_path = tmp_path / "starter-bundles.zip"

    bundle_path = build_bundle(out_path)

    assert bundle_path == out_path
    assert out_path.exists()

    with ZipFile(out_path, "r") as bundle:
        names = sorted(bundle.namelist())
        assert names == [
            "README.md",
            "claude-code/.claude-plugin/marketplace.json",
            "claude-code/README.md",
            "claude-code/plugins/notes-recover/.claude-plugin/plugin.json",
            "claude-code/plugins/notes-recover/.mcp.json",
            "claude-code/plugins/notes-recover/skills/notes-recover-mcp/SKILL.md",
            "codex/.codex/config.toml",
            "codex/README.md",
            "codex/marketplace.example.json",
            "codex/plugins/notes-recover/.codex-plugin/plugin.json",
            "codex/plugins/notes-recover/.mcp.json",
            "codex/plugins/notes-recover/skills/notes-recover-mcp/SKILL.md",
            "openclaw/README.md",
            "openclaw/workspace/notes-recover-mcp.sample.json",
            "openclaw/workspace/skills/notes-recover/SKILL.md",
        ]
        root_readme = bundle.read("README.md").decode("utf-8")
        assert "marketplace-format starter" in root_readme
        assert "fresh live read-back" in root_readme
        claude_readme = bundle.read("claude-code/README.md").decode("utf-8")
        assert "plugin plus marketplace-format surfaces" in claude_readme
        openclaw_readme = bundle.read("openclaw/README.md").decode("utf-8")
        assert "comparison-path starter" in openclaw_readme
