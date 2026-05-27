# Agent Navigation

## Repository Identity

- Project: NoteStore Lab
- Canonical public repo: `xiaojiou176-open/noteyard`
- Primary entrypoint: `notes-recovery`
- Host boundary: macOS only
- Working style: operate on copied evidence, never the live Notes store

## Public Source Of Truth

Use these files as the canonical public navigation surface:

- [README.md](./README.md)
- [DISTRIBUTION.md](./DISTRIBUTION.md)
- [llms.txt](./llms.txt)
- [INTEGRATIONS.md](./INTEGRATIONS.md)
- [ECOSYSTEM.md](./ECOSYSTEM.md)
- [USE_CASES.md](./USE_CASES.md)
- [CONTRIBUTING.md](./CONTRIBUTING.md)
- [CHANGELOG.md](./CHANGELOG.md)
- [SECURITY.md](./SECURITY.md)
- [SUPPORT.md](./SUPPORT.md)
- [LICENSE](./LICENSE)
- [CODEOWNERS](./CODEOWNERS)

## Repository Rules

- Keep tracked documentation in English.
- Keep public claims aligned with repo-owned evidence and fresh read-back only.
- Keep runtime artifacts, caches, logs, and agent work directories out of the
  tracked tree.
- Treat `.runtime-cache/`, `.agents/`, `.agent/`, `.codex/`, `.claude/`,
  `log/`, `logs/`, and `*.log` as local-only support surfaces.
- Preserve the baseline and optional-surface verification contracts documented
  in [CONTRIBUTING.md](./CONTRIBUTING.md).

## Evidence And Leak Discipline

- No-code-loss: preserve copied evidence, manifests, reports, and review
  artifacts as operator-owned records; prefer new timestamped outputs over
  in-place destructive rewrites.
- Zero-real-leak: keep tracked docs, screenshots, examples, and plugin metadata
  on synthetic, redacted, or public-safe material only; do not commit real
  Apple Notes content, private case-root artifacts, secrets, or personal
  absolute-path disclosures.
- Path hygiene: keep examples and docs on repo-owned relative paths and
  rebuildable support surfaces; do not normalize user-specific desktop paths as
  public contract.
- Support metadata is not a public support promise by itself; the supported
  public routes stay the ones documented in [SUPPORT.md](./SUPPORT.md).

## Host Safety Contract

- Keep this repository on copied evidence and repo-local rebuildable support
  surfaces only.
- Do not introduce broad host-cleanup helpers or shared-process termination
  paths.
- Never add `killall`, `pkill`, `kill -9`, `os.kill(...)`,
  `process.kill(...)`, `osascript`, `System Events`, `AppleEvent`,
  `loginwindow`, or Force Quit style automation.
- If a future contributor needs a local convenience action, keep it scoped to
  explicit repo-owned paths and user-invoked previews instead of shared GUI
  apps or unrelated host processes.

## Destructive Action Discipline

- Do not add helpers that mutate the live Notes store, erase copied evidence,
  or bulk-delete case-root material as part of the default workflow.
- Keep deletion, overwrite, and export-pruning actions explicit, narrowly
  scoped, previewable, and limited to repo-owned output paths.
- Do not turn storefront or registry metadata into proof of listing; external
  listing, marketplace, and read-back claims require fresh platform-side
  confirmation.
