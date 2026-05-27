# Codex Starter Bundle

This starter bundle turns the Noteyard MCP entrypoint into tracked Codex
artifacts for both project-local config and plugin-format packaging.

## Files

- `.codex/config.toml`
- `plugins/noteyard/.codex-plugin/plugin.json`
- `plugins/noteyard/.mcp.json`
- `plugins/noteyard/skills/noteyard-mcp/SKILL.md`
- `marketplace.example.json`

The bundled skill file is a host-specific derived copy. The canonical
independent skill surface lives at `skills/noteyard-case-review/`.

## Install path

1. For the lightest-weight path, copy `.codex/config.toml` into your project
   root as `.codex/config.toml`.
2. Replace `./output/Notes_Forensics_<run_ts>` with a real case root.
3. If you want plugin-format installation, copy `plugins/noteyard/` into a
   repo or personal Codex marketplace and merge `marketplace.example.json` into
   your real `.agents/plugins/marketplace.json`.

This bundle is public-ready for Codex's plugin format, but not officially
listed in an OpenAI-managed plugin directory.
