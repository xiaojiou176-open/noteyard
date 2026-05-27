# Semantic Retrieval Spike Readiness

Status: `conditional`
Last reviewed: `2026-04-02`
Scope: gate for a bounded semantic retrieval spike on top of the current
derived-artifact retrieval contract.

This file is not a shipped semantic feature contract.
It is a go/no-go gate that decides whether the next worker may open a tightly
scoped spike without dragging the repository away from its accepted identity.

## 1. What Is Already Ready

The current repository state is strong enough to support a *bounded* semantic
retrieval spike because these substrate conditions are already in place:

- the primary retrieval unit is locked to one case root at a time
- the derived-artifact catalog and selection tiers are written into a repo-owned
  contract SSOT
- `ask-case`, `ai-review`, and `notes-recovery-mcp` already consume the same
  shared retrieval spine
- the retrieval contract CI guard exists and currently passes
- the current retrieval hardening wave has fresh repo-side verification
- manual/platform/storefront leftovers are already separated from repo-side work

That means the next spike does **not** need to redesign the product identity or
re-open retrieval-contract basics.

## 2. What Is Not Ready Yet

The repository is **not** ready for direct semantic feature implementation until
the next worker first locks the spike frame itself.

These preconditions are still missing:

1. a written spike brief with one explicit hypothesis
2. an explicit non-goal list that forbids shipped-scope expansion
3. a decision on whether semantic ranking may only reorder *allowed artifacts*
   or may introduce new retrieval inputs
4. a local-only index/storage plan
5. a spike-only evaluation plan with reproducible fixtures and exit criteria
6. a rollback rule that leaves token-hit selection as the stable fallback

Without those six items, a semantic spike is too likely to become an accidental
product expansion instead of a controlled experiment.

## 3. Current Gate Decision

The gate is **open only for a bounded local spike prompt**.

The gate is **closed** for any of the following:

- shipping semantic retrieval as accepted product scope
- changing the primary retrieval unit away from one case root
- blending multiple case roots by default
- default cloud/vector retrieval
- hosted or remote semantic services
- any branding/story drift that makes the repository sound like a hosted AI
  platform or generic chat product

In plain language: the next worker may test a small local ranking experiment,
but may not turn that experiment into a new product promise.

## 4. Mandatory Spike Constraints

Any semantic retrieval spike must keep all of these constraints:

1. stay on derived artifacts only
2. keep the live Apple Notes store and raw copied evidence out of scope
3. keep explicit cloud opt-in semantics unchanged
4. preserve evidence-backed answers with confidence and uncertainty fields
5. preserve case-root-centric, local `stdio`-first, read-mostly MCP posture
6. preserve the current retrieval contract as the fallback and comparison
   baseline

If a proposed spike cannot satisfy all six constraints, the gate is closed.

## 5. Required Inputs Before A Spike Can Start

Before implementation begins, the next worker must produce a short spike brief
that answers all of these questions:

| Question | Required answer shape |
| --- | --- |
| What is the exact spike hypothesis? | One sentence |
| What remains stable? | Current retrieval contract + current product identity |
| What is allowed to change? | Ranking method only, unless explicitly approved |
| What is forbidden to change? | Retrieval unit, allowed-artifact boundary, hosted/cloud default, branding, manual/platform scope |
| How is success measured? | Spike-local eval checks and qualitative acceptance criteria |
| How does rollback work? | Delete/disable the spike path and fall back to token-hit selector |

If the next worker cannot answer those six questions before coding, the spike
must not start.

## 6. Absolute Prohibitions

The following remain prohibited even inside a spike:

- semantic search over raw copied evidence bodies
- semantic search over `DB_Backup/`, `Cache_Backup/`, or `Spotlight_Backup/`
- default cross-case semantic blending
- default cloud embeddings or remote vector services
- hosted review portals or team collaboration layers
- `.ai` / AI-first product repositioning
- HTTP / OpenAPI / SDK platformization
- treating discovery/front-door files as case evidence
- admitting unvalidated plugin outputs into default semantic intake

## 7. Minimum Verification For A Spike

The next worker may start the spike only if it also commits to the following
verification shape:

1. keep existing retrieval contract tests green
2. add spike-local tests or fixtures that prove semantic ranking is bounded
3. prove fallback to the current selector still works
4. prove semantic ranking does not change allowed-artifact boundaries
5. prove `ask-case`/`ai-review`/MCP still emit evidence-backed outputs instead
   of freeform answers

If those verification commitments are absent, the spike is not ready.

## 8. Escalate To Owner If Any Of These Become Necessary

The next worker must stop and escalate if the spike would require any of these
decisions:

- allowing semantic retrieval to add new artifact classes
- allowing cross-case semantic retrieval by default
- allowing default cloud embeddings or hosted vector infrastructure
- changing public product positioning or front-door copy
- treating plugin outputs as first-class semantic inputs before a typed plugin
  result contract exists

Those are owner-level product decisions, not spike-level implementation details.

## 9. Recommended Next Scope

The safest next step is:

1. keep the current retrieval hardening wave as accepted repo-side work
2. open a separate bounded semantic retrieval spike prompt
3. require that prompt to consume this file plus
   `DERIVED_ARTIFACT_RETRIEVAL_CONTRACT.md`
4. keep the spike local-only, one-case-root-only, and evaluation-first

Until that happens, semantic retrieval should remain a readiness topic, not an
active implementation stream.
