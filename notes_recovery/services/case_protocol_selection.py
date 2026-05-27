from __future__ import annotations

from typing import Any, Iterable

from .case_protocol_contract import (
    CaseResource,
    DEFAULT_TIER_A_SOURCE_IDS,
    DEFAULT_TIER_B_SOURCE_IDS,
    TOKEN_RE,
    spec_for_resource,
)

RESOURCE_WEIGHTS = {
    "review_index": 5.0,
    "verification_preview": 5.0,
    "verification_hit": 4.5,
    "pipeline_summary": 4.0,
    "timeline_summary": 4.0,
    "timeline_events": 3.5,
    "ai_triage_summary": 3.5,
    "ai_top_findings": 3.0,
    "case_manifest": 2.5,
    "run_manifest": 2.5,
    "report_excerpt": 2.0,
    "text_bundle_inventory": 2.0,
    "ai_next_questions": 1.5,
    "demo_case_tree": 3.0,
    "demo_verification_summary": 4.0,
    "demo_operator_brief": 3.0,
}


def selection_reason(item: dict[str, Any], *, matched: bool, injected: bool) -> str:
    spec = spec_for_resource(item)
    if matched and injected:
        return (
            f"{spec.default_selection_reason} "
            "Kept as a retrieval backbone even though stronger query matches filled the initial ranked set."
        )
    if matched:
        return f"{spec.default_selection_reason} Ranked as a direct match for the current question."
    if injected:
        return f"{spec.default_selection_reason} Added as a fallback so the one-case retrieval spine stays grounded."
    return spec.default_selection_reason


def tokenize_query(query: str) -> list[str]:
    tokens = [token.lower() for token in TOKEN_RE.findall(query)]
    seen: set[str] = set()
    unique_tokens: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        unique_tokens.append(token)
    return unique_tokens


def search_case_resources(
    resources: Iterable[CaseResource],
    query: str,
    *,
    max_results: int = 6,
) -> list[dict[str, Any]]:
    resource_list = list(resources)
    tokens = tokenize_query(query)
    scored: list[tuple[float, CaseResource]] = []
    for item in resource_list:
        base_weight = RESOURCE_WEIGHTS.get(item.kind, 1.0)
        lowered = item.content.lower()
        token_hits = sum(lowered.count(token) for token in tokens)
        score = token_hits * base_weight if tokens else base_weight
        if score <= 0 and tokens:
            continue
        scored.append((score, item))
    if not scored:
        scored = [(RESOURCE_WEIGHTS.get(item.kind, 1.0), item) for item in resource_list]
    scored.sort(
        key=lambda pair: (pair[0], RESOURCE_WEIGHTS.get(pair[1].kind, 1.0)),
        reverse=True,
    )
    results: list[dict[str, Any]] = []
    for score, item in scored[:max_results]:
        spec = spec_for_resource(item)
        results.append(
            {
                "source_id": item.source_id,
                "artifact": item.artifact,
                "path": item.relpath,
                "relpath": item.relpath,
                "kind": item.kind,
                "tier": spec.tier,
                "excerpt": item.excerpt,
                "score": round(float(score), 2),
            }
        )
    return results


def select_case_evidence(
    resources: Iterable[CaseResource],
    query: str,
    *,
    max_results: int = 6,
) -> list[dict[str, Any]]:
    resource_list = list(resources)
    query_tokens = tokenize_query(query)
    matched_ids: set[str] = set()
    if query_tokens:
        for item in resource_list:
            lowered = item.content.lower()
            if any(token in lowered for token in query_tokens):
                matched_ids.add(item.source_id)
    ranked_items = search_case_resources(resource_list, query, max_results=max_results)
    ranked_index = {item["source_id"]: item for item in ranked_items}
    all_items = {
        item.source_id: {
            "source_id": item.source_id,
            "artifact": item.artifact,
            "path": item.relpath,
            "relpath": item.relpath,
            "kind": item.kind,
            "tier": spec_for_resource(item).tier,
            "excerpt": item.excerpt,
            "score": 0.0,
        }
        for item in resource_list
    }

    selected_ids: list[str] = []
    injected_ids: set[str] = set()
    for source_id in DEFAULT_TIER_A_SOURCE_IDS:
        if source_id in all_items and source_id not in selected_ids:
            selected_ids.append(source_id)
            injected_ids.add(source_id)
    for source_id in DEFAULT_TIER_B_SOURCE_IDS:
        if source_id in all_items and source_id not in selected_ids and len(selected_ids) < max_results:
            selected_ids.append(source_id)
            injected_ids.add(source_id)
    for item in ranked_items:
        if item["source_id"] not in selected_ids and len(selected_ids) < max_results:
            selected_ids.append(item["source_id"])

    selected: list[dict[str, Any]] = []
    for source_id in selected_ids[:max_results]:
        base = dict(all_items[source_id])
        matched = source_id in matched_ids
        if matched:
            base["score"] = ranked_index[source_id]["score"]
        base["selection_reason"] = selection_reason(
            base,
            matched=matched,
            injected=source_id in injected_ids,
        )
        base["locator"] = None
        selected.append(base)
    return selected


def build_evidence_ref(
    item: dict[str, Any],
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    resolved_reason = (reason or "").strip() or str(item["selection_reason"])
    return {
        "source_id": item["source_id"],
        "artifact": item["artifact"],
        "path": item["path"],
        "relpath": item["relpath"],
        "kind": item["kind"],
        "selection_reason": resolved_reason,
        "score": item["score"],
        "locator": item["locator"],
        "reason": resolved_reason,
        "excerpt": item["excerpt"],
    }


def build_suggested_target(
    item: dict[str, Any],
    *,
    reason: str | None = None,
) -> dict[str, str]:
    resolved_reason = (reason or "").strip() or str(item["selection_reason"])
    return {
        "artifact": item["artifact"],
        "path": item["path"],
        "relpath": item["relpath"],
        "reason": resolved_reason,
    }


def build_artifact_priority_items(
    evidence_items: Iterable[dict[str, Any]],
    *,
    max_results: int = 4,
) -> list[dict[str, Any]]:
    priorities: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in evidence_items:
        source_id = str(item["source_id"])
        if source_id in seen:
            continue
        seen.add(source_id)
        priorities.append(
            {
                "artifact": str(item["artifact"]),
                "priority": len(priorities) + 1,
                "reason": str(item["selection_reason"]),
                "source_id": source_id,
                "tier": str(item["tier"]),
                "relpath": str(item["relpath"]),
                "kind": str(item["kind"]),
                "selection_reason": str(item["selection_reason"]),
            }
        )
        if len(priorities) >= max_results:
            break
    return priorities


def normalize_artifact_priority_items(
    raw_items: Iterable[dict[str, Any]],
    evidence_items: Iterable[dict[str, Any]],
    *,
    max_results: int = 4,
) -> list[dict[str, Any]]:
    evidence_list = list(evidence_items)
    if not evidence_list:
        return []

    evidence_by_source_id = {
        str(item["source_id"]): item for item in evidence_list if item.get("source_id")
    }
    evidence_by_source_id_lower = {
        source_id.lower(): item for source_id, item in evidence_by_source_id.items()
    }
    evidence_by_artifact = {
        str(item["artifact"]).strip().lower(): item
        for item in evidence_list
        if str(item.get("artifact", "")).strip()
    }

    priorities: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id", "")).strip()
        artifact = str(item.get("artifact", "")).strip()
        reason = str(item.get("reason", "")).strip()
        priority_raw = item.get("priority", len(priorities) + 1)
        try:
            priority = int(priority_raw)
        except (TypeError, ValueError):
            priority = len(priorities) + 1

        matched = None
        if source_id and source_id in evidence_by_source_id:
            matched = evidence_by_source_id[source_id]
        elif source_id and source_id.lower() in evidence_by_source_id_lower:
            matched = evidence_by_source_id_lower[source_id.lower()]
        elif artifact and artifact in evidence_by_source_id:
            matched = evidence_by_source_id[artifact]
        elif artifact and artifact.lower() in evidence_by_source_id_lower:
            matched = evidence_by_source_id_lower[artifact.lower()]
        elif artifact and artifact.lower() in evidence_by_artifact:
            matched = evidence_by_artifact[artifact.lower()]

        if matched is None:
            dedupe_key = source_id or artifact or f"artifact_priority_{index}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            priorities.append(
                {
                    "artifact": artifact or "unknown",
                    "priority": priority,
                    "reason": reason or "No reason provided.",
                    "source_id": source_id,
                }
            )
        else:
            canonical_source_id = str(matched["source_id"])
            if canonical_source_id in seen:
                continue
            seen.add(canonical_source_id)
            resolved_reason = reason or str(matched["selection_reason"])
            priorities.append(
                {
                    "artifact": str(matched["artifact"]),
                    "priority": priority,
                    "reason": resolved_reason,
                    "source_id": canonical_source_id,
                    "tier": str(matched["tier"]),
                    "relpath": str(matched["relpath"]),
                    "kind": str(matched["kind"]),
                    "selection_reason": resolved_reason,
                }
            )
        if len(priorities) >= max_results:
            break

    if priorities:
        priorities.sort(key=lambda item: int(item["priority"]))
        return priorities[:max_results]

    return build_artifact_priority_items(evidence_list, max_results=max_results)


__all__ = [
    "build_artifact_priority_items",
    "build_evidence_ref",
    "build_suggested_target",
    "normalize_artifact_priority_items",
    "search_case_resources",
    "select_case_evidence",
    "tokenize_query",
]
