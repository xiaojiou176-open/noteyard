# Noteyard OpenClaw-Compatible Bundle

This directory is a comparison-path companion bundle for OpenClaw-style hosts.

It is intentionally not an official OpenClaw listing. Instead, it packages the
same bounded Noteyard MCP launcher, plus a workspace skill, into one
portable bundle shape after the local copy-first lab already makes sense.

## What it includes

- `.claude-plugin/plugin.json`
- `.mcp.json`
- `bin/noteyard-mcp`
- `workspace/skills/noteyard/SKILL.md`

## Required environment

Set these before you use the launcher:

- `NOTEYARD_REPO_ROOT`
- `NOTEYARD_CASE_DIR`
- optional: `NOTEYARD_PYTHON`

The launcher uses `NOTEYARD_PYTHON` when present. Otherwise it falls back
to `$NOTEYARD_REPO_ROOT/.venv/bin/python`.
