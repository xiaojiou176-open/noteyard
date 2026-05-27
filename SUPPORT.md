# Support

## Public Support Routes

Use GitHub Issues for public bug reports, feature requests, and documentation
clarifications.

Use the repository issue templates so reports stay structured and reproducible.
If you are still evaluating the project from the outside, start with the root
README, [proof.html](./proof.html), and this support guide before opening a new
issue.

## What To Include

- The exact command you ran
- The macOS and Python version
- Any optional extras you installed
- A short log excerpt or screenshot when helpful

For newer protocol or AI surfaces, also include:

- whether you used `--demo` or a real case root
- the AI provider and whether `--allow-cloud` was involved
- for MCP issues: the transport, the tool/resource name, and the case-root shape you exposed
- for builder / local agent issues: which host you used
  (`Codex`, `Claude Code`, `OpenHands`, `OpenCode`, or another local runner)
  and whether you stayed on the MCP surface or parsed case-root artifacts directly

Do not post secrets, private evidence, live Apple Notes data, or sensitive
artifacts in public issues.

## Security Reports

Do not use public issues for vulnerability details.

Use [SECURITY.md](./SECURITY.md) and GitHub Security Advisories for private
security reporting.

## Scope Reminder

NotesRecover is a local macOS forensic toolkit.

Support is limited to the repository, its documented workflows, and the public
baseline or optional surfaces described in [README.md](./README.md) and
[CONTRIBUTING.md](./CONTRIBUTING.md).

Useful public entrypoints:

- Repository overview: <https://github.com/xiaojiou176-open/notes-recover>
- Issue tracker: <https://github.com/xiaojiou176-open/notes-recover/issues>
- Release feed: <https://github.com/xiaojiou176-open/notes-recover/releases>

Storefront settings such as GitHub description, topics, custom social preview,
and release-page copy remain maintainer-managed manual actions. Treat them as
storefront operations, not as repo runtime bugs.
