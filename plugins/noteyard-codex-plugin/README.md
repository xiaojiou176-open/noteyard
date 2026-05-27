# NotesRecover Codex Plugin

This is a Codex-format companion bundle for later host-specific installs around
NotesRecover's local case-review workflow.

It is built for one very specific job:

- keep recovery as the main product
- keep AI as a bounded review layer
- keep MCP on one explicit case root at a time

## What It Includes

- `.codex-plugin/plugin.json`
- `.mcp.json`
- `bin/notes-recover-mcp`
- `skills/notes-recover-case-review/SKILL.md`
- `examples/marketplace.json`

The canonical independent skill surface now lives at
`skills/notes-recover-case-review/`. The bundled skill file in this plugin is a
derived host copy that must stay in sync with that root-level canonical
surface.

## Required Environment

Set these before you use the plugin:

- `NOTES_RECOVER_REPO_ROOT`
- `NOTES_RECOVER_CASE_DIR`
- optional: `NOTES_RECOVER_PYTHON`

If `NOTES_RECOVER_PYTHON` is unset, the launcher uses
`$NOTES_RECOVER_REPO_ROOT/.venv/bin/python`.

## Install Into A Repo Marketplace

1. Copy this directory into your plugin tree.
2. Merge `examples/marketplace.json` into your real `.agents/plugins/marketplace.json`.
3. Restart Codex.
4. Install the plugin from your local marketplace.

This bundle is public-ready for Codex's plugin format, but OpenAI's
self-serve official Plugin Directory publishing is not open yet.
