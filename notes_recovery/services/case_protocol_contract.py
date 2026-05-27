from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

MAX_JSON_CHARS = 16_000
MAX_TEXT_CHARS = 6_000
MAX_CSV_ROWS = 12
EXCERPT_CHARS = 280

TOKEN_RE = re.compile(r"[A-Za-z0-9_:-]{3,}")

DERIVED_ARTIFACT_RETRIEVAL_CONTRACT_VERSION = "2026-04-02.v1"
PRIMARY_RETRIEVAL_UNIT = "one-case-root-at-a-time"
EVIDENCE_REF_SCHEMA_VERSION = "2026-04-02.v1"
TIER_A_ANCHOR = "tier_a_anchor"
TIER_B_STRUCTURE = "tier_b_structure"
TIER_C_ENRICHER = "tier_c_enricher"

DEFAULT_TIER_A_SOURCE_IDS = (
    "review_index",
    "verification_preview",
    "pipeline_summary",
)
DEFAULT_TIER_B_SOURCE_IDS = (
    "run_manifest",
    "case_manifest",
    "timeline_summary",
)

EVIDENCE_REF_FIELDS = (
    "source_id",
    "artifact",
    "relpath",
    "kind",
    "excerpt",
    "selection_reason",
    "score",
    "locator",
)

ABSOLUTE_RETRIEVAL_EXCLUSIONS = (
    "raw copied evidence bodies",
    "live Apple Notes store",
    "DB_Backup/",
    "Cache_Backup/",
    "Spotlight_Backup/",
    "absolute paths",
    "credentials",
    "secrets",
    "broad filesystem browse",
    "unvalidated plugin outputs",
    "storefront/discovery docs as case evidence",
    "hosted retrieval by default",
    "vector retrieval by default",
    "cloud retrieval by default",
    "cross-case blended retrieval without an explicit compare contract",
)


@dataclass(frozen=True)
class RetrievalArtifactSpec:
    source_id: str
    artifact: str
    kind: str
    tier: str
    default_selection_reason: str
    mode: str = "case-root"


@dataclass(frozen=True)
class CaseResource:
    source_id: str
    artifact: str
    relpath: str
    title: str
    content: str
    kind: str

    @property
    def excerpt(self) -> str:
        text = " ".join(self.content.split())
        if len(text) <= EXCERPT_CHARS:
            return text
        return text[:EXCERPT_CHARS].rstrip() + "..."


CASE_RESOURCE_SPECS = {
    "review_index": RetrievalArtifactSpec(
        source_id="review_index",
        artifact="Review index",
        kind="review_index",
        tier=TIER_A_ANCHOR,
        default_selection_reason="Tier A anchor for one-case review flow ordering.",
    ),
    "run_manifest": RetrievalArtifactSpec(
        source_id="run_manifest",
        artifact="Run manifest",
        kind="run_manifest",
        tier=TIER_B_STRUCTURE,
        default_selection_reason="Tier B structure artifact that anchors the per-run stage ledger.",
    ),
    "case_manifest": RetrievalArtifactSpec(
        source_id="case_manifest",
        artifact="Case manifest",
        kind="case_manifest",
        tier=TIER_B_STRUCTURE,
        default_selection_reason="Tier B structure artifact that inventories derived outputs for one case root.",
    ),
    "pipeline_summary": RetrievalArtifactSpec(
        source_id="pipeline_summary",
        artifact="Pipeline summary",
        kind="pipeline_summary",
        tier=TIER_A_ANCHOR,
        default_selection_reason="Tier A anchor that summarizes the copied-evidence workflow outcome.",
    ),
    "verification_preview": RetrievalArtifactSpec(
        source_id="verification_preview",
        artifact="Verification preview",
        kind="verification_preview",
        tier=TIER_A_ANCHOR,
        default_selection_reason="Tier A anchor that provides the fastest hit-oriented review surface.",
    ),
    "timeline_summary": RetrievalArtifactSpec(
        source_id="timeline_summary",
        artifact="Timeline summary",
        kind="timeline_summary",
        tier=TIER_B_STRUCTURE,
        default_selection_reason="Tier B structure artifact that grounds chronology before stronger conclusions.",
    ),
    "timeline_events": RetrievalArtifactSpec(
        source_id="timeline_events",
        artifact="Timeline events",
        kind="timeline_events",
        tier=TIER_C_ENRICHER,
        default_selection_reason="Tier C enricher that expands chronology beyond the summary layer.",
    ),
    "report_excerpt": RetrievalArtifactSpec(
        source_id="report_excerpt",
        artifact="HTML report excerpt",
        kind="report_excerpt",
        tier=TIER_C_ENRICHER,
        default_selection_reason="Tier C enricher that adds narrative context from the generated report surface.",
    ),
    "text_bundle_inventory": RetrievalArtifactSpec(
        source_id="text_bundle_inventory",
        artifact="Text bundle inventory",
        kind="text_bundle_inventory",
        tier=TIER_C_ENRICHER,
        default_selection_reason="Tier C enricher that summarizes review-friendly bundle contents.",
    ),
    "ai_triage_summary": RetrievalArtifactSpec(
        source_id="ai_triage_summary",
        artifact="AI triage summary",
        kind="ai_triage_summary",
        tier=TIER_C_ENRICHER,
        default_selection_reason="Tier C enricher that captures prior AI triage without replacing the core case spine.",
    ),
    "ai_top_findings": RetrievalArtifactSpec(
        source_id="ai_top_findings",
        artifact="AI top findings",
        kind="ai_top_findings",
        tier=TIER_C_ENRICHER,
        default_selection_reason="Tier C enricher that captures prior AI finding summaries for the same case root.",
    ),
    "ai_next_questions": RetrievalArtifactSpec(
        source_id="ai_next_questions",
        artifact="AI next questions",
        kind="ai_next_questions",
        tier=TIER_C_ENRICHER,
        default_selection_reason="Tier C enricher that suggests follow-up inspection targets.",
    ),
}

DEMO_RESOURCE_SPECS = {
    "demo_case_tree": RetrievalArtifactSpec(
        source_id="demo_case_tree",
        artifact="Demo case tree",
        kind="demo_case_tree",
        tier=TIER_B_STRUCTURE,
        default_selection_reason="Demo-only structure artifact that shows the public-safe case layout.",
        mode="demo-only",
    ),
    "demo_verification_summary": RetrievalArtifactSpec(
        source_id="demo_verification_summary",
        artifact="Demo verification summary",
        kind="demo_verification_summary",
        tier=TIER_A_ANCHOR,
        default_selection_reason="Demo-only Tier A anchor that mirrors the safest first inspection surface.",
        mode="demo-only",
    ),
    "demo_operator_brief": RetrievalArtifactSpec(
        source_id="demo_operator_brief",
        artifact="Demo operator brief",
        kind="demo_operator_brief",
        tier=TIER_C_ENRICHER,
        default_selection_reason="Demo-only Tier C enricher that explains the copy-first workflow in plain language.",
        mode="demo-only",
    ),
}

VERIFICATION_HIT_WILDCARD_SPEC = RetrievalArtifactSpec(
    source_id="verification_hit_*",
    artifact="Verification hit preview rows",
    kind="verification_hit",
    tier=TIER_C_ENRICHER,
    default_selection_reason="Tier C enricher that preserves bounded verification-hit preview rows.",
)


def spec_for_resource(resource: CaseResource | dict[str, Any]) -> RetrievalArtifactSpec:
    source_id = str(resource["source_id"] if isinstance(resource, dict) else resource.source_id)
    kind = str(resource["kind"] if isinstance(resource, dict) else resource.kind)
    artifact = str(resource["artifact"] if isinstance(resource, dict) else resource.artifact)
    if source_id in CASE_RESOURCE_SPECS:
        return CASE_RESOURCE_SPECS[source_id]
    if source_id in DEMO_RESOURCE_SPECS:
        return DEMO_RESOURCE_SPECS[source_id]
    if kind == "verification_hit":
        return RetrievalArtifactSpec(
            source_id=source_id,
            artifact=artifact,
            kind=kind,
            tier=TIER_C_ENRICHER,
            default_selection_reason="Tier C enricher that preserves a bounded verification-hit preview row.",
        )
    return RetrievalArtifactSpec(
        source_id=source_id,
        artifact=artifact,
        kind=kind,
        tier=TIER_C_ENRICHER,
        default_selection_reason="Tier C enricher permitted by the derived-artifact retrieval contract.",
    )


def retrieval_contract_artifacts() -> list[dict[str, str]]:
    specs = [
        *CASE_RESOURCE_SPECS.values(),
        *DEMO_RESOURCE_SPECS.values(),
        VERIFICATION_HIT_WILDCARD_SPEC,
    ]
    specs.sort(key=lambda item: (item.mode, item.tier, item.source_id))
    return [
        {
            "source_id": spec.source_id,
            "artifact": spec.artifact,
            "kind": spec.kind,
            "tier": spec.tier,
            "mode": spec.mode,
        }
        for spec in specs
    ]


def derived_artifact_retrieval_contract() -> dict[str, Any]:
    return {
        "version": DERIVED_ARTIFACT_RETRIEVAL_CONTRACT_VERSION,
        "primary_retrieval_unit": PRIMARY_RETRIEVAL_UNIT,
        "evidence_ref_schema_version": EVIDENCE_REF_SCHEMA_VERSION,
        "default_tier_a_source_ids": list(DEFAULT_TIER_A_SOURCE_IDS),
        "default_tier_b_source_ids": list(DEFAULT_TIER_B_SOURCE_IDS),
        "allowed_artifacts": retrieval_contract_artifacts(),
        "evidence_ref_fields": list(EVIDENCE_REF_FIELDS),
        "absolute_exclusions": list(ABSOLUTE_RETRIEVAL_EXCLUSIONS),
        "compare_contract": "case-diff",
        "plugin_contract": "plugins-validate",
        "default_cloud_vector_retrieval": "disabled",
    }


__all__ = [
    "ABSOLUTE_RETRIEVAL_EXCLUSIONS",
    "CASE_RESOURCE_SPECS",
    "CaseResource",
    "DEFAULT_TIER_A_SOURCE_IDS",
    "DEFAULT_TIER_B_SOURCE_IDS",
    "DEMO_RESOURCE_SPECS",
    "DERIVED_ARTIFACT_RETRIEVAL_CONTRACT_VERSION",
    "EVIDENCE_REF_FIELDS",
    "EVIDENCE_REF_SCHEMA_VERSION",
    "EXCERPT_CHARS",
    "MAX_CSV_ROWS",
    "MAX_JSON_CHARS",
    "MAX_TEXT_CHARS",
    "PRIMARY_RETRIEVAL_UNIT",
    "RetrievalArtifactSpec",
    "TIER_A_ANCHOR",
    "TIER_B_STRUCTURE",
    "TIER_C_ENRICHER",
    "TOKEN_RE",
    "VERIFICATION_HIT_WILDCARD_SPEC",
    "derived_artifact_retrieval_contract",
    "retrieval_contract_artifacts",
    "spec_for_resource",
]
