# NotesRecover Starter Bundles

This directory contains repo-owned companion starter artifacts for the current
host surfaces around NotesRecover.

These bundles do not claim official listing unless the target platform already
shows one on its public surface. The goal is simpler:

- make installation copy-paste-safe
- keep the case-root and MCP contract truthful
- give developers a real proof loop instead of prose-only examples

The canonical independent skill surface now lives at
`skills/notes-recover-case-review/`. Any skill file inside these starter bundles
is a host-specific derived copy, not the primary source of truth.

## Included bundles

| Bundle | Surface | What it gives you | Truth boundary |
| --- | --- | --- | --- |
| `codex/` | Codex local/plugin marketplace starter | a tracked `.codex/config.toml` example plus a plugin-format bundle you can load through a local Codex marketplace | public-ready starter only, not an official Codex Plugin Directory listing |
| `claude-code/` | Claude Code plugin + marketplace starter | a marketplace-format root and a minimal plugin that packages NotesRecover onboarding as a Claude Code plugin surface | plugin-ready starter only, not already listed in an Anthropic-managed marketplace |
| `openclaw/` | OpenClaw comparison-path starter | a sample MCP config and a workspace skill starter for OpenClaw-compatible local installs | comparison-path starter only, not an official OpenClaw listing or ClawHub publication |

## Allowed claims

- `repo-owned starter bundle shipped`
- `plugin-ready` when the artifact validates against the host's local validator
- `marketplace-format starter` when the host exposes a marketplace format and
  this repo ships the required files
- `comparison-path starter` when the artifact is intentionally not the primary
  front-door claim

## Forbidden claims

- `officially listed` without fresh live read-back from the target platform
- `official Codex plugin` without an OpenAI-managed public plugin surface
- `official OpenClaw integration` without fresh OpenClaw-side listing proof
- `host plugin platform` as the core repo identity
