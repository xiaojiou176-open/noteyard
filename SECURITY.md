# Security Policy

## Supported Scope

This repository is intended for local forensic workflows on macOS copies of
Apple Notes data.

The current protocol surface is also intentionally narrow:

- `notes-recovery-mcp` is a local `stdio`-first MCP server, not a default
  network-exposed HTTP service
- cloud-backed AI/provider paths remain explicit opt-in rather than default
  network behavior

## Host-safety Boundary

This repository is not a host-control or desktop automation tool.

Security-sensitive changes must not introduce:

- broad host cleanup or shared-process termination helpers
- `killall`, `pkill`, `kill -9`, `os.kill(...)`, or `process.kill(...)`
- `osascript`, `System Events`, `AppleEvent`, `loginwindow`, or Force Quit
  style automation

Repo-local convenience actions may only operate on repo-owned paths and
copied-evidence outputs. They must not target shared GUI apps or unrelated
host processes.

## Reporting a Vulnerability

Please do not disclose suspected vulnerabilities in a public issue first.

Use **GitHub Security Advisories** as the canonical private reporting channel
for this repository.

For release-readiness reviews on the canonical GitHub repository, use
`scripts/ci/check_release_readiness.py` to confirm the current hosting state
instead of assuming the advisory channel is still enabled from memory.

Share a private report there with:

- A short summary of the issue
- Steps to reproduce it
- Impact and any affected commands or files
- A minimal proof of concept if one exists
- Whether the issue concerns the case-root boundary, MCP resource/tool
  exposure, AI provider/network path, or public-safe export boundary

If GitHub Security Advisories are **not** enabled, this repository should be
treated as temporarily lacking a private reporting channel. In that case:

1. do **not** publish exploit details in a public issue
2. open a minimal public issue that only requests a private reporting path
3. wait for the maintainer to enable GitHub Security Advisories or publish a
   dedicated private contact before sending vulnerability details

Use [SUPPORT.md](./SUPPORT.md) only for normal public support. Do not route
vulnerability details through the public support path.

## Ownership Boundary

The current single-maintainer review owner for security-sensitive changes is
`@xiaojiou176`.

The canonical public repository is expected to stay under the
`xiaojiou176-open` GitHub organization, with branch protection and required
pull request reviews enforced on `main`.

## Current Limits

- A dedicated security mailbox is **not** published yet
- GitHub Security Advisories should remain the default private channel
- Public issues are acceptable only for requesting a private channel, not for
  sharing vulnerability details
- The deterministic required checks on `main` stay limited to the branch
  protection contexts enforced on the canonical repository
- CodeQL remains part of the security review surface, but it is not treated as
  a required merge gate in the current branch-protection policy

## Security Automation Boundary

- Treat GitHub Secret Scanning, push protection, and the release-readiness audit
  as the primary deterministic security checks for current publication claims
- Treat CodeQL as a pinned, scheduled, and pull-request-visible analysis lane,
  but not as a required branch-protection context unless the maintainers
  explicitly tighten that policy later
- Do not add third-party API or quota-dependent security steps to the default
  `push` / `pull_request` required chain

## Response Expectations

- Initial triage target: 7 business days
- Status updates are provided when reproduction succeeds or a fix is planned
- Public disclosure should wait until a mitigation or fix is available
