# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and uses milestone-style entries so
the public repository surface stays readable for users evaluating the project.

## [Unreleased]

### Added

- `notes-recovery doctor` as a front-door readiness check for the copied-evidence workflow
- `review_index.md` as the operator-facing navigation layer inside case roots
- `notes-recovery ai-review` for AI-assisted triage on derived review artifacts
- `notes-recovery ask-case` for evidence-backed case question answering
- `notes-recovery-mcp` as a local stdio-first read-mostly MCP server
- `.[mcp]` as an optional protocol extra and `extras-ai-mcp` as the matching CI lane
- `notes-recovery plugins-validate` for plugin contract validation
- `notes-recovery case-diff` for bounded cross-run / cross-case manifest and review-surface comparison
- `server.json` and the README MCP marker for MCP Registry-ready metadata
- a Codex plugin bundle under `plugins/notes-recover-codex-plugin/`
- a Claude Code plugin bundle under `plugins/notes-recover-claude-plugin/`
- a Git-backed Claude Code marketplace manifest at `.claude-plugin/marketplace.json`
- `scripts/release/build_distribution_bundles.py` for packaging Codex, Claude Code, and OpenClaw-compatible bundles
- `scripts/release/check_pypi_publish_readiness.py` for MCP/PyPI package-alignment, build, and `twine check` verification before external publishing
- a richer dashboard review cockpit with case-root selection, resource inventory, AI review quick view, and bounded case-diff preview

### Changed

- The public front door now treats `notes-recovery demo` as the public-safe
  first-look truth, with `ai-review`, `ask-case`, and MCP proof sitting on top
  of the same copy-first story
- The repository now treats host-safety as a tracked contract: root docs,
  pre-commit, CI, and repo-surface tests all enforce a no-host-control /
  no-broad-cleanup boundary
- The public-facing repo surface now includes dedicated use-case, ecosystem-fit,
  and builder-guide pages so AI / MCP / agent discovery stays sharper without
  pretending the project is a hosted platform
- Root-level contract files remain the only tracked public documentation
  surface; stale Pages/docs-live wording was removed from the repository story
- README, CI, pre-push, and repo-surface tests now share one public-story truth
  guardrail instead of relying on badge or release placeholders
- The public demo and release-facing bundle story now treat synthetic AI proof
  as part of the review-layer narrative instead of keeping it implicit
- The live landing now leads with a proof-first developer front door, stronger
  proof CTAs, and a command-first `llms.txt` intake for AI/agent readers
- The Codex / Claude Code wrapper story now includes project-scoped wrapper
  examples, the Codex path-base correction, and matching discovery guardrails
- Host onboarding now ships tracked distribution artifacts while keeping
  official marketplace/listing claims out of the contract until external
  read-back exists
- The tracked social preview asset chain now includes a fixed 1280x640 export
  path and regression coverage for both image dimensions and current public
  truth tokens

- Repo-owned storefront source assets under `assets/readme/` and
  `assets/social/`
- A `check_public_story_truth.py` guardrail to stop stale release, Pages, and
  visual-asset claims from drifting back in

### Notes

- GitHub Release `v0.1.0` is now published on the repository Releases page
- Release `v0.1.0` now includes the `notes-recover-public-safe-demo-v0.1.0.zip`
  synthetic public demo bundle
- The GitHub Pages landing now acts as the minimal live front door for the
  current shipped story
- `llms.txt`, `robots.txt`, and `sitemap.xml` now expose the current public
  contract to AI crawlers and search engines
- GitHub description, topics, custom social preview upload, and any future
  `.ai` landing-page work remain manual external actions
- Custom social preview remains a GitHub Settings task until it is manually
  uploaded and verified

## [0.1.0] - 2026-03-25

### Added

- Public-surface README rewrite focused on value proposition, quickstart, demo
  artifacts, and trust signals
- Sanitized demo artifacts for case outputs, manifests, and verification
  summaries

### Changed

- The repository front door now presents NotesRecover as a CLI-first,
  copy-first Apple Notes recovery workflow instead of a policy-heavy project
  index
- Public links now separate conversion surfaces (README) from deeper contract
  and contribution surfaces

### Notes

- Public release readiness is audited separately via
  `scripts/ci/check_release_readiness.py --strict` before any release-facing
  claim is treated as live
