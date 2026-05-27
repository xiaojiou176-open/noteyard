# NotesRecover Public Skill Pack

These files are the public-safe subset of the repo's skill distribution story.

What this pack is for:

- keeping OpenHands/extensions and ClawHub-style submissions on a repo-owned
  folder instead of ad hoc copy-paste
- keeping public wording aligned across the canonical skill surface, builder
  docs, and marketplace-facing packaging
- giving hosts and reviewers one portable folder they can inspect without
  inheriting maintainer-only task-board or archive context

What this pack is not:

- a dump of `.agents/skills/`
- proof of a live listing on OpenHands/extensions, Glama, or Docker MCP Catalog
- proof that the live secondary ClawHub skill listing automatically means a live
  OpenClaw bundle listing or accepted host-wrapper lane
- a hosted runtime or remote MCP deployment

Current public-safe contents:

- `notes-recover-case-review/`
  - OpenHands/extensions-friendly public skill folder
  - ClawHub-style manifest with semver-ready listing metadata
  - today the secondary ClawHub public-skill listing is already live
  - one derived copy of the canonical `skills/notes-recover-case-review/SKILL.md`

Public-safe inclusion test:

- keep a file here only if it still works as repo-scoped guidance without
  private machine paths, owner-session assumptions, or task-board state
- pull it back out if it starts depending on maintainer-only closeout rituals
- keep official-listing claims outside this pack unless fresh platform-side
  read-back exists

Use this pack as the copyable skill-folder lane for OpenHands/extensions or a
ClawHub-style publish flow. Pair it with the root-level public contract files
when you need the full product boundary:

- `README.md`
- `DISTRIBUTION.md`
- `INTEGRATIONS.md`
- `ECOSYSTEM.md`
