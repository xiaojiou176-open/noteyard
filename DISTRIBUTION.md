# Distribution Surface

This file is the exact claim boundary for Noteyard's public distribution
story.

Treat it as a later-lane ledger, not as the repo's front-door product sentence.
The front door stays local, copy-first, operator-first, and case-root-centric.
Treat the copied-evidence workbench as the main cargo. Registry, package, and
public-skill lanes are companion lanes around that workbench, not replacement
front doors.

Use it when you need to answer:

- what counts as official
- what counts as public-ready only
- which surfaces are still later-lane prep
- what still requires Wave 2 or manual external action

## Public Distribution Matrix

| Surface | Official public surface exists | Repo-owned artifact shipped | Wave 1 posture | Current truthful boundary |
| --- | --- | --- | --- | --- |
| MCP Registry | yes, the official MCP Registry exists and is still documented as a preview surface | yes: `server.json` and `notes-recovery-mcp` | current pure-MCP companion lane | fresh registry read-back exists for the current package lane, but keep the front door on the local case-root workflow instead of leading with registry status |
| Cline MCP Marketplace | yes, the public intake issue lane exists | yes: `server.json`, `README.md`, and repo-root install proof are already aligned to the current stdio-first MCP story | companion review lane | the intake is submitted on [`cline/mcp-marketplace#1324`](https://github.com/cline/mcp-marketplace/issues/1324), but it is still review-pending and not listed live |
| Codex | yes, the official Codex plugin directory exists, but third-party official-directory submission is still coming soon | yes: `plugins/noteyard-codex-plugin/` | companion plugin lane | repo-owned Codex bundle shipped; do not claim official Codex directory listing |
| Claude Code | yes, official plugin and marketplace surfaces exist | yes: `plugins/noteyard-claude-plugin/` plus root `.claude-plugin/marketplace.json` | companion plugin lane | repo-owned Claude plugin and marketplace metadata shipped; do not claim Anthropic-managed listing without fresh read-back |
| OpenClaw | yes, the official ClawHub public registry exists | yes: `plugins/noteyard-openclaw-bundle/` | comparison-path companion lane | the secondary ClawHub public-skill listing is live, but the shipped OpenClaw-compatible bundle still does not prove an official OpenClaw listing or first-class host wrapper acceptance |
| OpenHands/extensions | yes, the official OpenHands public extensions registry exists | yes: `public-skills/noteyard-case-review/` plus canonical `skills/noteyard-case-review/` | portable public skill lane | public skill folder shipped; the current thread is submission-done plus changes-requested, so do not claim a live OpenHands/extensions listing until maintainer acceptance lands |
| Glama | yes, the public Add Server and hosted MCP surface exists | yes: `glama.json`, `Dockerfile`, and the canonical GHCR target | Wave 2 metadata prep | repo-owned Glama metadata and Docker-facing inputs shipped; do not claim a live Glama listing without fresh Glama-side read-back |
| Docker MCP Catalog | yes, the official curated Docker MCP Catalog exists | yes: `Dockerfile`, `scripts/release/check_docker_surface.py`, and the canonical GHCR target | Wave 2 container/catalog prep | Docker-facing container inputs shipped; do not claim a live Docker catalog listing without fresh Docker-side submission/read-back |

## Repo-Owned Artifacts

### Stronger distribution artifacts

- `plugins/noteyard-codex-plugin/`
- `plugins/noteyard-claude-plugin/`
- `plugins/noteyard-openclaw-bundle/`
- `skills/noteyard-case-review/`
- `public-skills/noteyard-case-review/`
- `.claude-plugin/marketplace.json`
- `glama.json`
- `server.json`
- `scripts/release/build_distribution_bundles.py`
- `Dockerfile`

### Onboarding starter artifacts

- `starter-bundles/codex/`
- `starter-bundles/claude-code/`
- `starter-bundles/openclaw/`
- `scripts/release/build_starter_bundles_bundle.py`

## Independent Skill Surface

The canonical independent skill surface now lives at
`skills/noteyard-case-review/`.

That directory is the single repo-owned SSOT for the skill package:

- `SKILL.md` is the canonical operator guidance
- `manifest.yaml` is the canonical publish/readiness metadata
- plugin and starter skill files are derived host copies, not parallel SSOTs

This means the repository can now truthfully say "independent skill surface
shipped" or "independent skill ready" without claiming any official directory
listing.

For public skill-folder registries, the portable listing packet now lives at
`public-skills/noteyard-case-review/`.

That packet is intentionally separate from the canonical skill SSOT:

- canonical truth still lives in `skills/noteyard-case-review/`
- the public packet adds semver-ready listing metadata for ClawHub-style
  publication
- the public packet adds an OpenHands/extensions-facing README so external
  reviewers do not need to infer the install story from internal bundle paths
- today that packet already has a live secondary ClawHub listing, while the
  OpenHands submission still remains in platform review

## Package Surface

The canonical installable package surface for this repository is PyPI:

- package name: `noteyard`
- `server.json` points at the PyPI package because the current MCP publication
  story is Python-first
- this is the intended PyPI package identifier and version for the current repo
  contract: `noteyard==0.1.0.post1`
- fresh package read-back exists for this package lane, but keep package status
  as supporting distribution truth rather than the first sentence of the
  product story

There is no tracked npm package surface in the current public contract:

- no `package.json`
- no npm install path in the public docs
- no shipped TypeScript SDK or generated client surface yet

That means npm is not a missing canonical package lane for this repository
today. If a future npm surface ever ships, it must become an explicit new
public contract rather than an implied comparison path.

## Docker And Catalog Later Surface

Docker-ready local container surface shipped:

- `Dockerfile`
- `.dockerignore`
- `scripts/release/check_docker_surface.py`

This container path is for local reproducibility of the CLI and stdio MCP
surface. Treat image and catalog read-back as later validation work, not as the
main claim for this repo. That is still not proof of a hosted deployment,
multi-tenant backend, live Glama listing, or Docker MCP Catalog listing.

The canonical image target, if and when later validation is refreshed, is:

- `ghcr.io/xiaojiou176-open/noteyard:0.1.0.post1`
- optional convenience tag: `ghcr.io/xiaojiou176-open/noteyard:latest`

`glama.json` is now the repo-owned metadata side of the Glama story. It makes
the intended maintainer identity explicit, but it does **not** prove a live
Glama listing or hosted deployment by itself.

Do not claim a live Glama listing without fresh Glama-side read-back.

## Proof Loops

### Common proof path

```bash
./.venv/bin/notes-recovery demo
./.venv/bin/notes-recovery ask-case --demo --question "What should I inspect first?"
./.venv/bin/notes-recovery-mcp --help
```

### Claude Code plugin validation

```bash
claude plugin validate plugins/noteyard-claude-plugin
claude plugin validate .
```

### Distribution archive build

```bash
./.venv/bin/python scripts/release/build_distribution_bundles.py --out-dir ./dist
./.venv/bin/python scripts/release/build_starter_bundles_bundle.py --out ./dist/noteyard-host-starters.zip
```

### MCP Registry descriptor boundary

`server.json` is the metadata side of the MCP Registry story. Keep the
repo-side claim narrow: the stdio-first MCP descriptor is shipped in-repo, and
fresh registry/package read-back supports that lane without replacing the
copy-first front-door story.

The repo-side publish-readiness proof command is:

```bash
./.venv/bin/python scripts/release/check_pypi_publish_readiness.py
```

## Allowed Claims

- "`server.json` captures the current stdio-first MCP descriptor for Noteyard"
- "the Cline MCP Marketplace intake is submitted and review-pending on `cline/mcp-marketplace#1324`"
- "PyPI is the canonical installable package surface for this repository today"
- "public-ready Codex plugin bundle shipped"
- "repo-owned Claude Code plugin and marketplace metadata shipped"
- "OpenClaw-compatible bundle shipped"
- "independent skill surface shipped"
- "OpenHands/extensions-friendly public skill folder shipped"
- "repo-owned Glama-ready metadata shipped"
- "Docker-ready local container surface shipped"

## Forbidden Claims

- "public directory acceptance" without fresh external read-back
- "Cline MCP Marketplace is listed live" without fresh marketplace read-back
- "MCP Registry submission completed" without fresh registry read-back
- "registry metadata proves MCP Registry listing" without fresh registry read-back
- "official Codex plugin directory listing" without OpenAI-managed listing proof
- "official Anthropic marketplace listing" without fresh marketplace read-back
- "live OpenClaw bundle listing" without fresh OpenClaw-side acceptance proof
- "live OpenHands/extensions listing" without fresh OpenHands PR/read-back
- "official npm package" or "npm is the canonical install path" without a real shipped npm package surface
- "host-side accepted skill" without fresh host-side read-back
- "hosted service" or "multi-tenant platform" for the Docker surface
