from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from notes_recovery.services import ai_review
from notes_recovery.services.case_protocol import (
    build_evidence_ref,
    build_case_resources,
    build_demo_resources,
    build_suggested_target,
    select_case_evidence,
)

ASK_CASE_PROMPT_VERSION = "2026-03-31.v1"
VALID_CONFIDENCE = {"high", "medium", "low"}


def _normalize_confidence(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in VALID_CONFIDENCE:
        return lowered
    return "low"


def _default_payload(question: str, evidence_items: list[dict[str, Any]]) -> dict[str, Any]:
    top_refs = list(evidence_items)[:3]
    if top_refs:
        lead = top_refs[0]
        answer = (
            f"Based on the current derived review artifacts, start with `{lead['artifact']}`"
            f" at `{lead['path']}` and validate the question against the other cited surfaces before drawing a stronger conclusion."
        )
        uncertainty = (
            "This answer is limited to the currently indexed derived artifacts. "
            "If you need stronger proof, rerun or inspect the suggested next targets directly."
        )
        confidence = "medium" if lead.get("score", 0) > 0 else "low"
    else:
        answer = (
            "I do not have enough indexed derived evidence to answer this question confidently yet."
        )
        uncertainty = (
            "No derived artifact matched the question strongly enough, so the safest next step is to inspect the review index and verification outputs manually."
        )
        confidence = "low"
    suggested = [build_suggested_target(item) for item in top_refs]
    evidence_refs = [build_evidence_ref(item) for item in top_refs]
    return {
        "answer": answer,
        "confidence": confidence,
        "uncertainty": uncertainty,
        "evidence_refs": evidence_refs,
        "suggested_next_targets": suggested,
    }


def _build_prompt(question: str, evidence_items: list[dict[str, Any]]) -> tuple[str, str]:
    system_prompt = (
        "You are an evidence-backed review assistant for Apple Notes recovery cases. "
        "Only answer from the provided derived artifacts. "
        "Do not invent evidence or cite sources that were not provided. "
        "Return strict JSON with keys: answer, confidence, uncertainty, evidence_refs, suggested_next_targets. "
        "confidence must be one of high|medium|low. "
        "Each evidence_refs item must contain source_id and reason. "
        "Each suggested_next_targets item must contain artifact and reason."
    )
    user_prompt = json.dumps(
        {
            "prompt_version": ASK_CASE_PROMPT_VERSION,
            "question": question,
            "evidence_items": evidence_items,
        },
        ensure_ascii=True,
        indent=2,
    )
    return system_prompt, user_prompt


def _normalize_payload(payload: dict[str, Any], evidence_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    answer = str(payload.get("answer", "")).strip()
    if not answer:
        raise RuntimeError("Ask-case output is missing `answer`.")
    confidence = _normalize_confidence(str(payload.get("confidence", "low")))
    uncertainty = str(payload.get("uncertainty", "")).strip()

    evidence_refs: list[dict[str, Any]] = []
    for item in payload.get("evidence_refs", []):
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id", "")).strip()
        if source_id not in evidence_index:
            continue
        evidence = evidence_index[source_id]
        evidence_refs.append(
            build_evidence_ref(
                evidence,
                reason=str(item.get("reason", "")).strip() or evidence["selection_reason"],
            )
        )

    suggested_next_targets: list[dict[str, str]] = []
    for item in payload.get("suggested_next_targets", []):
        if isinstance(item, dict):
            artifact = str(item.get("artifact", "")).strip()
            reason = str(item.get("reason", "")).strip() or "No reason provided."
        else:
            artifact = str(item).strip()
            reason = "Suggested by the ask-case provider."
        if not artifact:
            continue
        suggested_next_targets.append({"artifact": artifact, "reason": reason})

    return {
        "answer": answer,
        "confidence": confidence,
        "uncertainty": uncertainty,
        "evidence_refs": evidence_refs,
        "suggested_next_targets": suggested_next_targets,
    }


def render_ask_case_result(payload: dict[str, Any]) -> str:
    lines = [
        "Ask case",
        "",
        f"Question: {payload['question']}",
        f"Confidence: {payload['confidence']}",
    ]
    if payload.get("uncertainty"):
        lines.append(f"Uncertainty: {payload['uncertainty']}")
    lines.extend(
        [
            "",
            "Answer",
            payload["answer"],
            "",
            "Evidence refs",
        ]
    )
    for item in payload["evidence_refs"]:
        lines.append(
            f"- {item['source_id']} -> {item['artifact']} ({item['path']}) — {item['reason']}"
        )
        if item.get("excerpt"):
            lines.append(f"  Excerpt: {item['excerpt']}")
    if payload["suggested_next_targets"]:
        lines.extend(["", "Suggested next targets"])
        for item in payload["suggested_next_targets"]:
            lines.append(f"- {item['artifact']} — {item['reason']}")
    return "\n".join(lines) + "\n"


def run_ask_case(
    *,
    root_dir: Optional[Path],
    question: str,
    demo: bool,
    repo_root: Path,
    provider: Optional[str],
    model: Optional[str],
    ollama_base_url: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    allow_cloud: bool = False,
    timeout_sec: int = 120,
) -> dict[str, Any]:
    question = question.strip()
    if not question:
        raise RuntimeError("`ask-case` requires a non-empty `--question`.")
    if demo:
        resources = build_demo_resources(repo_root, include_ai_review=True)
    else:
        if root_dir is None:
            raise RuntimeError("A case root is required unless `--demo` is used.")
        resources = build_case_resources(root_dir, include_ai_review=True)

    evidence_items = select_case_evidence(resources, question, max_results=6)
    evidence_index = {item["source_id"]: item for item in evidence_items}
    provider_config = ai_review.resolve_provider_config(
        provider=provider,
        model=model,
        demo=demo,
        ollama_base_url=ollama_base_url,
        openai_api_key=openai_api_key,
        allow_cloud=allow_cloud,
        timeout_sec=timeout_sec,
    )
    system_prompt, user_prompt = _build_prompt(question, evidence_items)

    if provider_config.provider == "mock":
        normalized = _default_payload(question, evidence_items)
    elif provider_config.provider == "ollama":
        raw = ai_review._call_ollama(  # type: ignore[attr-defined]
            config=provider_config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        text = str(raw.get("response", "")).strip()
        normalized = _normalize_payload(
            ai_review._extract_json_payload(text),  # type: ignore[attr-defined]
            evidence_index,
        )
    elif provider_config.provider == "openai":
        raw = ai_review._call_openai(  # type: ignore[attr-defined]
            config=provider_config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        text = str(raw.get("output_text", "")).strip()
        if not text:
            parts: list[str] = []
            for item in raw.get("output", []):
                for content in item.get("content", []):
                    content_text = str(content.get("text", "")).strip()
                    if content_text:
                        parts.append(content_text)
            text = "\n".join(parts).strip()
        normalized = _normalize_payload(
            ai_review._extract_json_payload(text),  # type: ignore[attr-defined]
            evidence_index,
        )
    else:
        raise RuntimeError(f"Unsupported ask-case provider: {provider_config.provider}")

    if not normalized["evidence_refs"]:
        normalized = _default_payload(question, evidence_items)

    return {
        "question": question,
        "provider": provider_config.provider,
        "model": provider_config.model,
        "source_mode": "demo" if demo else "case-root",
        "prompt_version": ASK_CASE_PROMPT_VERSION,
        **normalized,
    }
