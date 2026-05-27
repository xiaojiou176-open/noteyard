# Claude Navigation

## What This Repository Is

Noteyard is a CLI-first Apple Notes forensic recovery toolkit for macOS.

The canonical execution chain is:

`notes-recovery CLI -> parser/handlers -> services -> core pipeline -> timestamped case outputs`

## What To Read First

- [README.md](./README.md) for product shape and public contract
- [CONTRIBUTING.md](./CONTRIBUTING.md) for verification and CI expectations
- [SECURITY.md](./SECURITY.md) for private vulnerability reporting
- [SUPPORT.md](./SUPPORT.md) for public support routing

## Guardrails

- Do not introduce tracked runtime or cache surfaces.
- Do not add localized or non-English public documentation.
- Do not weaken the baseline smoke contract without updating the matching
  guardrail scripts and CI lanes.
- Keep examples non-public until redistributable material exists.
- Follow the Host Safety Contract in [AGENTS.md](./AGENTS.md): no broad host
  cleanup, shared-process killing, or desktop-wide automation.
