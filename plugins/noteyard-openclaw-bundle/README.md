# NotesRecover OpenClaw-Compatible Bundle

This directory is a comparison-path companion bundle for OpenClaw-style hosts.

It is intentionally not an official OpenClaw listing. Instead, it packages the
same bounded NotesRecover MCP launcher, plus a workspace skill, into one
portable bundle shape after the local copy-first lab already makes sense.

## What it includes

- `.claude-plugin/plugin.json`
- `.mcp.json`
- `bin/notes-recover-mcp`
- `workspace/skills/notes-recover/SKILL.md`

## Required environment

Set these before you use the launcher:

- `NOTES_RECOVER_REPO_ROOT`
- `NOTES_RECOVER_CASE_DIR`
- optional: `NOTES_RECOVER_PYTHON`

The launcher uses `NOTES_RECOVER_PYTHON` when present. Otherwise it falls back
to `$NOTES_RECOVER_REPO_ROOT/.venv/bin/python`.
