# Builder Guide

This repository already exposes a usable local integration substrate.

The key is to start from what is real today, not from what could exist later.
Treat this guide as a later builder lane around the local lab, not as the first
sentence that defines the product.

## Current Stable Builder Surfaces

| Surface | What it is | Where it lives |
| --- | --- | --- |
| CLI | the primary operator and automation surface | `notes-recovery` |
| Case root contract | the stable directory and manifest layout | `notes_recovery/case_contract.py` |
| Review-safe shared artifacts | manifests, summaries, verification previews, review index, AI outputs | one timestamped case root |
| MCP | local tool/resource interface for case-root consumption | `notes-recovery-mcp` |
| Compare surface | bounded case-root comparison | `notes-recovery case-diff` |

## Discovery Entry For AI Crawlers

If an external AI crawler or agent-reader needs the fastest truthful summary of
the current public contract, start with:

- `llms.txt`

That file is a discovery surface, not an API contract and not an SDK surface.
It exists to point builders and AI readers at the right public documents first,
instead of making them infer the product boundary from scattered pages.

## Recommended Integration Order

1. Start from one existing case root
2. Read the case manifest and review index
3. Decide whether file-level consumption is enough
4. If you want a tool/resource surface, switch to `notes-recovery-mcp`
5. Only design a higher-level client after your builder path is stable

## MCP Entry

Start the server:

```bash
notes-recovery-mcp --case-dir ./output/Notes_Forensics_<run_ts>
```

Equivalent direct Python entrypoint:

```bash
.venv/bin/python -m notes_recovery.mcp.server --case-dir ./output/Notes_Forensics_<run_ts>
```

For Codex / Claude Code style hosts, use that command inside the host's local
MCP configuration wrapper. The wrapper format can differ by host, but the
stable executable contract is:

- local stdio transport
- one explicit case root
- read-mostly derived-output access
- no hosted API assumptions

Host notes:

- Codex and Claude Code are both good current examples of hosts that fit the shipped local stdio MCP surface in this repo.
- Treat the local stdio command above as the stable contract even when the surrounding host wrapper differs by version or client.
- Treat remote-connector-first hosts as comparison paths here because this repo does not ship a hosted or remote MCP deployment.
- OpenClaw-style hosts stay in the comparison bucket for now, but this repo now ships an OpenClaw-compatible bundle build path instead of a docs-only comparison note.

Public-ready host artifacts now shipped in-repo:

- Codex plugin bundle: `plugins/notes-recover-codex-plugin/`
- Claude Code plugin bundle: `plugins/notes-recover-claude-plugin/`
- Claude marketplace manifest: `.claude-plugin/marketplace.json`
- OpenClaw-compatible bundle build: `.venv/bin/python scripts/release/build_distribution_bundles.py --out-dir ./dist`
- OpenHands/extensions-friendly public skill folder: `public-skills/notes-recover-case-review/`

Fast host smoke checklist:

1. Run `notes-recovery demo`
2. Run `notes-recovery ask-case --demo --question "What should I inspect first?"`
3. Start `.venv/bin/python -m notes_recovery.mcp.server --case-dir ./output/Notes_Forensics_<run_ts>`
4. Register that exact direct Python command in your host wrapper before you design anything larger

Minimal wrapper examples:

Codex project `.codex/config.toml` example:

```toml
[mcp_servers.notes-recover]
command = "../.venv/bin/python"
args = [
  "-m",
  "notes_recovery.mcp.server",
  "--case-dir",
  "./output/Notes_Forensics_<run_ts>",
]
cwd = ".."
```

Claude Code project `.mcp.json` example:

```json
{
  "mcpServers": {
    "notes-recover": {
      "command": ".venv/bin/python",
      "args": [
        "-m",
        "notes_recovery.mcp.server",
        "--case-dir",
        "./output/Notes_Forensics_<run_ts>"
      ]
    }
  }
}
```

Keep these examples intentionally minimal:

- the executable command is the real contract
- the surrounding host wrapper can still evolve by client version
- one case root per server entry stays the safest current default
- Codex project config resolves relative paths from `.codex/`, so `../.venv/bin/python`
  plus `cwd = ".."` keeps the server rooted at the repository top level

Tracked distribution artifacts:

- `plugins/notes-recover-codex-plugin/.codex-plugin/plugin.json`
- `plugins/notes-recover-claude-plugin/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `server.json`

Package the installable archives with:

```bash
.venv/bin/python scripts/release/build_distribution_bundles.py --out-dir ./dist
```

Those bundles are repo-owned companion artifacts, not official marketplace or
registry listings.

For the MCP lane specifically, `server.json` is still the repo-owned metadata
layer around the same local stdio workflow. Keep the repo-side claim narrow
here: the package/install surface is real, and fresh package/registry
read-back now exists for the current MCP and PyPI lane, but this guide still
keeps that supporting truth behind the local case-root story. Use
[DISTRIBUTION.md](./DISTRIBUTION.md) when you need the current package,
registry, or listing boundary.

Current PyPI install path:

```bash
python -m pip install notes-recover==0.1.0.post1
```

Repo-side metadata/build-readiness proof:

```bash
.venv/bin/python scripts/release/check_pypi_publish_readiness.py
```

OpenClaw-style install path:

- Build the OpenClaw-compatible archive with `build_distribution_bundles.py`.
- Install the local archive with `openclaw plugins install ./dist/notes-recover-openclaw-bundle-v0.1.0.zip`.
- A live ClawHub public-skill listing now exists for the secondary packet lane, but that does not turn this OpenClaw-compatible bundle into a live OpenClaw bundle listing.

Current design intent:

- local `stdio` first
- read-only / read-mostly
- case-root-centric
- derived-artifact-first

## Host Packaging Status

| Surface | Status | Guidance |
| --- | --- | --- |
| Codex plugin bundle | shipped | use `plugins/notes-recover-codex-plugin/` and a real local marketplace entry |
| Claude Code marketplace-format starter | shipped | use `.claude-plugin/marketplace.json` plus `plugins/notes-recover-claude-plugin/` without turning it into proof of an Anthropic-managed listing |
| OpenClaw-compatible bundle | shipped | build the local archive from `plugins/notes-recover-openclaw-bundle/`; the secondary ClawHub public-skill listing is live, but it does not prove a live OpenClaw bundle listing |
| canonical independent skill surface | shipped | use `skills/notes-recover-case-review/` as the canonical independent skill surface; plugin/starter skill files are host-specific derived copies |
| OpenHands/extensions-friendly public skill folder | shipped | use `public-skills/notes-recover-case-review/` when you need a standalone skill-folder packet for OpenHands/extensions or similar registries; today the same packet is live on ClawHub while the OpenHands thread remains changes-requested |
| repo-owned host plugin | shipped as installable bundles | the shipped plugins are installable surfaces, but installability does not imply official listing |

## Container Later Surface

The truthful container story for this repository is:

- one Docker image
- local CLI and local `stdio` MCP usage
- copied case roots mounted in by the operator
- no hosted-service claim

Canonical build:

```bash
docker build -t notes-recover:0.1.0.post1 .
```

Public-safe demo smoke:

```bash
docker run --rm notes-recover:0.1.0.post1 notes-recovery demo
```

Bounded MCP entrypoint:

```bash
docker run --rm -i \
  -v "$PWD/output:/cases:ro" \
  --entrypoint notes-recovery-mcp \
  notes-recover:0.1.0.post1 \
  --case-dir /cases/Notes_Forensics_<run_ts>
```

The canonical image target for later validation is
`ghcr.io/xiaojiou176-open/notes-recover:0.1.0.post1`, with `latest`
as the optional convenience tag. Keep describing GHCR as an OCI/package surface, not as
proof of a live Glama or Docker catalog listing.

`docker-compose` is intentionally absent here. This repo is a local CLI / MCP
workbench, not a multi-service stack. The container image is the repo-side
maximum we can claim truthfully today; it does not prove a live Glama listing.

The Glama metadata side now lives in `glama.json`. That file is enough to make
the Add Server handoff explicit for a Docker-backed submission, but it still
does not prove a live Glama listing or hosted runtime by itself.

## API / SDK Status

| Surface | Status | Guidance |
| --- | --- | --- |
| HTTP API | not shipped | do not promise REST access today |
| OpenAPI | not shipped | do not describe this repo as an API platform today |
| generated client | not shipped | no official generated client exists yet |
| TypeScript SDK | future path only | reasonable later, after the shared case/MCP contract is frozen |
| Python SDK | later than TS SDK | current Python entry is the repo itself, not a separate SDK |

## Future Substrate Path

If the project later grows a builder-facing SDK, the safest order is:

1. keep the case-root contract stable
2. keep MCP tool/resource semantics stable
3. extract shared typed resource/tool payloads
4. add a thin TypeScript client first
5. add a Python SDK only if external builder demand justifies it

## Explicit Non-Goals Today

- hosted API gateway
- remote multi-tenant review backend
- write-capable MCP by default
- generic plug-in platform claims
- official marketplace claims without fresh external read-back
- “SDK platform” wording without a real generated client or package
