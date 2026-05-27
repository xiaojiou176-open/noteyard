# Derived Artifact Retrieval Contract

Status: `v1`
Version: `2026-04-02.v1`
Scope: repo-owned SSOT for one-case / one-case-root derived-artifact retrieval.

This repository intentionally keeps its tracked contract files at the repo root.
The retrieval contract lives here for the same reason: it is part of the
active repository control surface, and adding a new `docs/` tree just to hold
this contract would introduce a second documentation topology.

## Stable Identity

This contract exists inside the current repository identity:

- copy-first Apple Notes recovery and review toolkit for macOS
- AI remains a bounded review/Q&A layer
- MCP remains a local stdio-first, read-mostly protocol surface
- discovery/front-door surfaces are not case evidence
- this repository is not a hosted AI platform, portal, or generic chat product

## Primary Retrieval Unit

The primary retrieval unit is exactly one case root at a time.

- Canonical value: `one-case-root-at-a-time`
- Retrieval operates on derived artifacts attached to one copied-evidence case root
- Cross-case blended retrieval is not part of the default contract
- Cross-case comparison must use an explicit compare contract such as
  `notes-recovery case-diff`

## Allowed Derived Artifacts v1

### Tier A anchors

These form the default retrieval spine for a single case root:

| `source_id` | Artifact | Kind |
| --- | --- | --- |
| `review_index` | Review index | `review_index` |
| `verification_preview` | Verification preview | `verification_preview` |
| `pipeline_summary` | Pipeline summary | `pipeline_summary` |
| `demo_verification_summary` | Demo verification summary | `demo_verification_summary` |

### Tier B structure

These keep retrieval grounded in the current case structure:

| `source_id` | Artifact | Kind |
| --- | --- | --- |
| `run_manifest` | Run manifest | `run_manifest` |
| `case_manifest` | Case manifest | `case_manifest` |
| `timeline_summary` | Timeline summary | `timeline_summary` |
| `demo_case_tree` | Demo case tree | `demo_case_tree` |

### Tier C enrichers

These may refine an answer or add context, but they do not replace the Tier A/B
spine:

| `source_id` | Artifact | Kind |
| --- | --- | --- |
| `timeline_events` | Timeline events | `timeline_events` |
| `report_excerpt` | HTML report excerpt | `report_excerpt` |
| `text_bundle_inventory` | Text bundle inventory | `text_bundle_inventory` |
| `ai_triage_summary` | AI triage summary | `ai_triage_summary` |
| `ai_top_findings` | AI top findings | `ai_top_findings` |
| `ai_next_questions` | AI next questions | `ai_next_questions` |
| `verification_hit_*` | Verification hit preview rows | `verification_hit` |
| `demo_operator_brief` | Demo operator brief | `demo_operator_brief` |

## Selection Discipline

The shared selector must follow these rules:

1. Retrieval starts from one case root or one demo surface, never from a broad
   repository crawl.
2. Tier A anchors are injected first when they exist.
3. Tier B structure artifacts are injected next so the answer stays grounded in
   manifests and chronology.
4. Tier C enrichers may fill the remaining slots based on query ranking.
5. Token-hit weighted ranking is the current selector implementation.
6. Semantic retrieval is not part of this contract and must remain a future,
   explicitly scoped spike.

## Evidence Ref Schema v1

The canonical evidence-ref schema is:

| Field | Meaning |
| --- | --- |
| `source_id` | Stable retrieval identifier inside the shared artifact catalog |
| `artifact` | Human-readable artifact label |
| `relpath` | Case-root-relative path |
| `kind` | Shared resource kind |
| `excerpt` | Bounded preview text |
| `selection_reason` | Why this artifact entered the current retrieval set |
| `score` | Query ranking score |
| `locator` | Optional future locator field for row/offset/section precision |

Compatibility note:

- `path` may still appear as a compatibility alias of `relpath` in current CLI
  or MCP payloads.
- `reason` may still appear as a compatibility alias of `selection_reason` in
  current CLI or MCP payloads.
- New retrieval consumers must treat `relpath` as canonical and keep
  `selection_reason` / `score` intact.

## Consumer Roles

- `ask-case`
  - consumes the shared selector output
  - returns evidence refs on the schema above
- `ai-review`
  - may keep its own prompt/output format
  - must source its retrieval context, manifest evidence refs, and normalized
    artifact priority payloads from the same shared artifact spine
- `notes-recovery-mcp`
  - retrieval-facing resources, case inspection, and selector-backed evidence
    lookup must stay on the same shared artifact contract
  - bounded write tools are adjacent workflow tools, not retrieval inputs
- future semantic retrieval
  - must extend this contract instead of replacing it

## Cross-Case Compare Boundary

- `notes-recovery case-diff` is an explicit compare contract
- it compares manifests and review-surface presence
- it must not become the default one-case retrieval path
- raw copied-evidence body diffs remain outside this contract

## Plugin Boundary

- `notes-recovery plugins-validate` is a bounded plugin contract checker
- `Plugins_Output/` is not part of the default retrieval input set
- unvalidated plugin outputs are excluded
- future plugin-derived retrieval must wait for a typed, validated plugin result
  contract

## MCP Retrieval vs Write Tools

Retrieval and bounded write tools must stay layered:

- retrieval reads derived artifacts and case summaries
- retrieval-facing MCP tools such as `inspect_case_artifact` and
  `select_case_evidence` must expose the shared selector / evidence-ref
  contract instead of consumer-local field shapes
- bounded write tools such as `run_verify`, `run_report`, `build_timeline`, and
  `public_safe_export` may create new derived artifacts
- those tools do not authorize broad filesystem browsing or live-store access
- those tools do not change the primary retrieval unit

## Absolute Exclusions

These must not enter default retrieval:

- raw copied evidence bodies
- live Apple Notes store
- `DB_Backup/`
- `Cache_Backup/`
- `Spotlight_Backup/`
- absolute paths
- credentials
- secrets
- broad filesystem browse
- unvalidated plugin outputs
- storefront/discovery docs as case evidence
- hosted retrieval by default
- vector retrieval by default
- cloud retrieval by default
- cross-case blended retrieval without an explicit compare contract

## Change Rule

Any change to this contract must update, in the same change:

1. this file
2. shared retrieval code in `notes_recovery/services/case_protocol.py`
3. affected consumer tests
4. the retrieval contract CI guard
