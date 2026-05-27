# NotesRecover Claude Code Plugin

This directory is a Claude Code companion bundle for later host-specific
installs. It is not the repo's flagship public lane, and it is not proof of an
Anthropic-managed listing.

It bundles:

- a plugin manifest
- a plugin-root `.mcp.json`
- a launcher that keeps the server pinned to one explicit case root

## Required Environment

Set these before you enable the plugin:

- `NOTES_RECOVER_REPO_ROOT`
- `NOTES_RECOVER_CASE_DIR`
- optional: `NOTES_RECOVER_PYTHON`

The bundled launcher uses `NOTES_RECOVER_PYTHON` when present. Otherwise it
falls back to `$NOTES_RECOVER_REPO_ROOT/.venv/bin/python`.

## Public Distribution Surface

The repository root ships `.claude-plugin/marketplace.json`, so the repository
itself can be added as a Claude Code marketplace.

Example:

```bash
claude plugin marketplace add xiaojiou176-open/notes-recover
claude plugin install notes-recover-claude-plugin@notes-recover-plugins
```

This plugin directory is also the source used for the OpenClaw-compatible
bundle archive built by `scripts/release/build_distribution_bundles.py`.
