# Noteyard Claude Code Plugin

This directory is a Claude Code companion bundle for later host-specific
installs. It is not the repo's flagship public lane, and it is not proof of an
Anthropic-managed listing.

It bundles:

- a plugin manifest
- a plugin-root `.mcp.json`
- a launcher that keeps the server pinned to one explicit case root

## Required Environment

Set these before you enable the plugin:

- `NOTEYARD_REPO_ROOT`
- `NOTEYARD_CASE_DIR`
- optional: `NOTEYARD_PYTHON`

The bundled launcher uses `NOTEYARD_PYTHON` when present. Otherwise it
falls back to `$NOTEYARD_REPO_ROOT/.venv/bin/python`.

## Public Distribution Surface

The repository root ships `.claude-plugin/marketplace.json`, so the repository
itself can be added as a Claude Code marketplace.

Example:

```bash
claude plugin marketplace add xiaojiou176-open/noteyard
claude plugin install noteyard-claude-plugin@noteyard-plugins
```

This plugin directory is also the source used for the OpenClaw-compatible
bundle archive built by `scripts/release/build_distribution_bundles.py`.
