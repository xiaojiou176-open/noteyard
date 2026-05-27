# Use Cases

This repository is strongest when you treat it as a local Apple Notes recovery
and review workbench, not as a hosted AI assistant.

## 1. Recovery Operator First Look

Best entry:

- `notes-recovery demo`
- `notes-recovery doctor`

Why it fits:

- you get one timestamped case root
- you see manifests, verification previews, and operator-facing outputs
- nothing touches private evidence or the live Notes store during the demo path

## 2. AI-Assisted Case Triage

Best entry:

- `notes-recovery ai-review --dir <case-root>`
- `notes-recovery ask-case --dir <case-root> --question "..."`

Why it fits:

- AI summarizes evidence that already exists in the case root
- AI suggests next inspection targets instead of pretending to be the recovery engine
- `ask-case` cites which derived artifacts it used

This is a workflow copilot pattern, not a generic chatbot.

## 3. Local Agent Consumption Through MCP

Best entry:

- `notes-recovery-mcp --case-dir <case-root>`

Why it fits:

- resources and tools stay case-root-centric
- the server is local `stdio` first
- the default stance is read-only / read-mostly

This is the cleanest current entrypoint for Codex / Claude Code style local
agent workflows.

## 4. Compare Two Case Roots

Best entry:

- `notes-recovery case-diff --dir-a <case-a> --dir-b <case-b>`

Why it fits:

- you can compare manifests and review-surface presence across two runs
- the command avoids raw copied-evidence body diffs
- it acts like a replay / compare diagnosis helper for operators

## Comparisons

### Versus ad hoc SQLite browsing

This repo gives you:

- one case root
- one review index
- one manifest trail
- optional AI-assisted review
- optional MCP consumption

Instead of:

- one-off queries
- untracked temporary files
- no shared artifact map

### Versus a generic AI assistant

This repo does **not** try to be a universal assistant.

It is narrower and more useful when you already have:

- a copied Apple Notes case
- a need to inspect evidence safely
- a need to summarize, question, compare, and hand off review artifacts

## Current Non-Goals

- hosted SaaS review portal
- write-capable MCP by default
- generic autonomy platform
- AI-first repo rename
- `.ai` as the primary shipped product identity
