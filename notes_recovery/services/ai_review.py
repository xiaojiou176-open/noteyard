from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from notes_recovery.case_contract import (
    CASE_DIR_AI_REVIEW,
    prefixed_case_dir,
)
from notes_recovery.core.pipeline import REDACTED_CASE_ROOT
from notes_recovery.io import ensure_dir
from notes_recovery.services.case_protocol import (
    build_artifact_priority_items,
    build_case_resources,
    build_demo_resources,
    derived_artifact_retrieval_contract,
    normalize_artifact_priority_items,
    select_case_evidence,
)
from notes_recovery.services.review_index import update_review_index_ai_section

AI_REVIEW_PROMPT_VERSION = "2026-03-31.v1"
DEFAULT_AI_PROVIDER = "ollama"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"


@dataclass(frozen=True)
class AiProviderConfig:
    provider: str
    model: str
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    demo_mode: bool = False
    timeout_sec: int = 120
    api_key: str = ""


def _resource_text(resources: dict[str, Any], source_id: str) -> str:
    resource = resources.get(source_id)
    if resource is None:
        return ""
    return str(resource.content)


def _resource_json(resources: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    resource = resources.get(source_id)
    if resource is None:
        return None
    try:
        payload = json.loads(resource.content)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _verification_hit_previews(resources: dict[str, Any]) -> list[dict[str, str]]:
    previews: list[dict[str, str]] = []
    for source_id, resource in resources.items():
        if not source_id.startswith("verification_hit_"):
            continue
        try:
            payload = json.loads(resource.content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            previews.append({key: str(value) for key, value in payload.items()})
    return previews


def _build_context_from_resources(resources: list[Any], *, source_mode: str) -> dict[str, Any]:
    resource_lookup = {item.source_id: item for item in resources}
    return {
        "source_mode": source_mode,
        "case_root": REDACTED_CASE_ROOT,
        "input_sources": [item.relpath for item in resources],
        "input_evidence_refs": select_case_evidence(resources, "", max_results=6),
        "retrieval_contract": derived_artifact_retrieval_contract(),
        "artifacts": {
            "review_index": _resource_text(resource_lookup, "review_index"),
            "run_manifest": _resource_json(resource_lookup, "run_manifest"),
            "case_manifest": _resource_json(resource_lookup, "case_manifest"),
            "pipeline_summary": _resource_text(resource_lookup, "pipeline_summary"),
            "verification_preview": _resource_text(resource_lookup, "verification_preview"),
            "verification_hits_preview": _verification_hit_previews(resource_lookup),
            "timeline_summary": _resource_json(resource_lookup, "timeline_summary"),
            "timeline_events": _resource_json(resource_lookup, "timeline_events"),
            "report_excerpt": _resource_text(resource_lookup, "report_excerpt"),
            "text_bundle_inventory": _resource_text(resource_lookup, "text_bundle_inventory"),
            "demo_case_tree": _resource_text(resource_lookup, "demo_case_tree"),
            "demo_operator_brief": _resource_text(resource_lookup, "demo_operator_brief"),
        },
        "guardrails": {
            "derived_output_first": True,
            "raw_evidence_included": False,
            "absolute_paths_redacted": True,
            "live_store_accessed": False,
        },
    }


def _build_case_context(root_dir: Path) -> dict[str, Any]:
    resources = build_case_resources(root_dir, include_ai_review=False)
    return _build_context_from_resources(resources, source_mode="case-root")


def _build_demo_context(repo_root: Path) -> dict[str, Any]:
    resources = build_demo_resources(repo_root, include_ai_review=False)
    return _build_context_from_resources(resources, source_mode="demo")


def build_ai_review_context(
    *,
    root_dir: Optional[Path],
    demo: bool,
    repo_root: Path,
) -> dict[str, Any]:
    if demo:
        return _build_demo_context(repo_root)
    if root_dir is None:
        raise RuntimeError("A case root is required unless --demo is used.")
    return _build_case_context(root_dir)


def build_ai_review_prompts(context: dict[str, Any]) -> tuple[str, str]:
    system_prompt = (
        "You are an AI review assistant for Apple Notes recovery cases. "
        "Recovery remains primary; you only triage derived review artifacts. "
        "Do not claim certainty beyond the evidence. "
        "Return strict JSON with keys: summary, top_findings, next_questions, artifact_priority. "
        "Each top finding must include title, signal_strength (high|medium|low), evidence. "
        "Each artifact priority item should preserve the provided artifact labels, should include source_id when available, "
        "and must include artifact, priority, reason."
    )
    user_prompt = json.dumps(
        {
            "prompt_version": AI_REVIEW_PROMPT_VERSION,
            "task": (
                "Summarize the case, prioritize artifacts, separate stronger from weaker signals, "
                "and suggest the next human questions."
            ),
            "context": context,
        },
        ensure_ascii=True,
        indent=2,
    )
    return system_prompt, user_prompt


def _extract_json_payload(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise RuntimeError("AI provider returned an empty response.")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError("AI provider response did not contain a JSON object.")
        return json.loads(text[start : end + 1])


def _normalize_payload(
    payload: dict[str, Any],
    *,
    evidence_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    summary = str(payload.get("summary", "")).strip()
    if not summary:
        raise RuntimeError("AI review output is missing `summary`.")

    findings: list[dict[str, str]] = []
    for item in payload.get("top_findings", []):
        if not isinstance(item, dict):
            continue
        findings.append(
            {
                "title": str(item.get("title", "")).strip() or "Untitled finding",
                "signal_strength": str(item.get("signal_strength", "medium")).strip().lower(),
                "evidence": str(item.get("evidence", "")).strip() or "No evidence explanation provided.",
            }
        )

    questions = [
        str(item).strip()
        for item in payload.get("next_questions", [])
        if str(item).strip()
    ]

    priorities = normalize_artifact_priority_items(
        (
            item
            for item in payload.get("artifact_priority", [])
            if isinstance(item, dict)
        ),
        evidence_items or [],
        max_results=4,
    )

    if not findings:
        findings.append(
            {
                "title": "Review the verification and report surfaces first",
                "signal_strength": "medium",
                "evidence": "The AI provider did not return structured findings, so the default operator guidance is to start from verification and report artifacts.",
            }
        )
    if not questions:
        questions = [
            "Which artifact contains the strongest match preview and why?",
            "Which findings still need manual verification before they can be trusted?",
            "What should the operator inspect next after the highest-priority artifact?",
        ]
    return {
        "summary": summary,
        "top_findings": findings,
        "next_questions": questions,
        "artifact_priority": sorted(priorities, key=lambda item: item["priority"]),
    }


def resolve_provider_config(
    *,
    provider: Optional[str],
    model: Optional[str],
    demo: bool,
    ollama_base_url: Optional[str],
    openai_api_key: Optional[str] = None,
    allow_cloud: bool = False,
    timeout_sec: int,
) -> AiProviderConfig:
    resolved_provider = (provider or os.environ.get("NOTES_AI_PROVIDER") or "").strip().lower()
    if not resolved_provider:
        resolved_provider = "mock" if demo else DEFAULT_AI_PROVIDER

    if resolved_provider == "mock":
        if not demo:
            raise RuntimeError("The mock AI provider is reserved for `--demo`. Use `--provider ollama` for real case reviews.")
        return AiProviderConfig(provider="mock", model="deterministic-demo", demo_mode=True, timeout_sec=timeout_sec)

    if resolved_provider not in {"ollama", "openai"}:
        raise RuntimeError(
            "Unsupported AI provider. Round 3 implements `ollama` for local reviews, `openai` for explicit cloud opt-in, and `mock` for `--demo`."
        )

    resolved_model = (
        model
        or (os.environ.get("NOTES_AI_OPENAI_MODEL") if resolved_provider == "openai" else None)
        or os.environ.get("NOTES_AI_OLLAMA_MODEL")
        or os.environ.get("NOTES_AI_MODEL")
        or ""
    ).strip()
    if not resolved_model:
        raise RuntimeError(
            "No AI model is configured. Set `--model` or the matching NOTES_AI_* model variable before running `ai-review`."
        )

    resolved_base_url = ""
    resolved_api_key = ""
    if resolved_provider == "ollama":
        resolved_base_url = (
            ollama_base_url
            or os.environ.get("NOTES_AI_OLLAMA_BASE_URL")
            or DEFAULT_OLLAMA_BASE_URL
        ).strip()
    else:
        if not allow_cloud and os.environ.get("NOTES_AI_ALLOW_CLOUD", "").strip().lower() not in {"1", "true", "yes", "on"}:
            raise RuntimeError(
                "The OpenAI provider is cloud-backed. Re-run with `--allow-cloud` only after confirming that derived-output-only review is acceptable for this case."
            )
        resolved_api_key = (
            openai_api_key
            or os.environ.get("NOTES_AI_OPENAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ).strip()
        if not resolved_api_key:
            raise RuntimeError(
                "The OpenAI provider requires NOTES_AI_OPENAI_API_KEY or OPENAI_API_KEY."
            )

    return AiProviderConfig(
        provider=resolved_provider,
        model=resolved_model,
        base_url=resolved_base_url,
        timeout_sec=timeout_sec,
        api_key=resolved_api_key,
    )


def _generate_mock_payload(context: dict[str, Any]) -> dict[str, Any]:
    artifacts = context.get("artifacts", {})
    input_evidence_refs = context.get("input_evidence_refs", [])
    has_verification = bool(artifacts.get("verification_preview"))
    has_timeline = bool(artifacts.get("timeline_summary"))
    has_report = bool(artifacts.get("report_excerpt"))
    has_review_index = bool(artifacts.get("review_index"))

    findings = []
    priorities = build_artifact_priority_items(input_evidence_refs, max_results=4)

    if has_review_index:
        findings.append(
            {
                "title": "The review index anchors the operator workflow",
                "signal_strength": "high",
                "evidence": "The shared retrieval spine keeps the review index in the first inspection tier, so the operator starts with workflow context before diving into narrower artifacts.",
            }
        )
    if has_verification:
        findings.append(
            {
                "title": "Verification provides the fastest first-pass signal",
                "signal_strength": "high",
                "evidence": "A verification preview is available, so the operator can quickly inspect ranked hits before diving into larger artifacts.",
            }
        )
    if has_report:
        findings.append(
            {
                "title": "The HTML report is a strong narrative companion",
                "signal_strength": "medium",
                "evidence": "A report excerpt exists, which means query/carve/plugin results can be reviewed in a richer offline surface.",
            }
        )
    if has_timeline:
        findings.append(
            {
                "title": "Timeline output can confirm or weaken sequence-based claims",
                "signal_strength": "medium",
                "evidence": "A timeline summary is present, so chronology can be used to separate stronger from weaker stories.",
            }
        )

    if context.get("source_mode") == "demo":
        summary = (
            "This synthetic demo already shows a reviewable workflow shape. Start with the verification summary, "
            "then use the operator brief to understand why the case stayed copy-first and safe to share."
        )
        questions = [
            "Which synthetic artifact best demonstrates the first human review step?",
            "If this were a real case, which derived output would you inspect before touching deeper artifacts?",
            "What evidence is still absent from the demo because it intentionally avoids private case data?",
        ]
    else:
        summary = (
            "This case is ready for AI-assisted triage on derived outputs only. "
            "Start from the review index and verification preview, then confirm chronology and richer context with timeline and report artifacts."
        )
        questions = [
            "Which high-priority artifact should the operator inspect immediately after the review index?",
            "Which current findings are still weak signals that need manual confirmation?",
            "Which artifact would best strengthen or falsify the current leading hypothesis?",
        ]

    return {
        "summary": summary,
        "top_findings": findings,
        "next_questions": questions,
        "artifact_priority": priorities,
    }


def _generate_ollama_payload(
    *,
    config: AiProviderConfig,
    system_prompt: str,
    user_prompt: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = _call_ollama(
        config=config,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    text = str(payload.get("response", "")).strip()
    return _normalize_payload(
        _extract_json_payload(text),
        evidence_items=evidence_items,
    )


def _generate_openai_payload(
    *,
    config: AiProviderConfig,
    system_prompt: str,
    user_prompt: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = _call_openai(
        config=config,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    text = str(payload.get("output_text", "")).strip()
    if not text:
        parts: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                content_text = str(content.get("text", "")).strip()
                if content_text:
                    parts.append(content_text)
        text = "\n".join(parts).strip()
    return _normalize_payload(
        _extract_json_payload(text),
        evidence_items=evidence_items,
    )


def _call_ollama(
    *,
    config: AiProviderConfig,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    try:
        import httpx
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The Ollama provider requires the optional AI dependencies. Install `python -m pip install -e .[ai]` first."
        ) from exc

    with httpx.Client(timeout=float(config.timeout_sec)) as client:
        response = client.post(
            f"{config.base_url.rstrip('/')}/api/generate",
            json={
                "model": config.model,
                "system": system_prompt,
                "prompt": user_prompt,
                "format": "json",
                "stream": False,
            },
        )
        response.raise_for_status()
        return response.json()


def _call_openai(
    *,
    config: AiProviderConfig,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    try:
        import httpx
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The OpenAI provider requires the optional AI dependencies. Install `python -m pip install -e .[ai]` first."
        ) from exc

    with httpx.Client(timeout=float(config.timeout_sec)) as client:
        response = client.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.model,
                "input": [
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": system_prompt}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_prompt}],
                    },
                ],
            },
        )
        response.raise_for_status()
        return response.json()


def _write_markdown(path: Path, title: str, lines: list[str]) -> None:
    ensure_dir(path.parent)
    body = [f"# {title}", "", *lines, ""]
    path.write_text("\n".join(body), encoding="utf-8")


def write_ai_review_outputs(
    out_dir: Path,
    payload: dict[str, Any],
    *,
    provider_config: AiProviderConfig,
    context: dict[str, Any],
    root_dir: Optional[Path],
    run_ts: str,
) -> dict[str, str]:
    ensure_dir(out_dir)
    triage_path = out_dir / "triage_summary.md"
    findings_path = out_dir / "top_findings.md"
    questions_path = out_dir / "next_questions.md"
    priority_path = out_dir / "artifact_priority.json"
    manifest_path = out_dir / "ai_review_manifest.json"

    _write_markdown(
        triage_path,
        "AI Review Triage Summary",
        [
            f"- Provider: `{provider_config.provider}`",
            f"- Model: `{provider_config.model}`",
            f"- Source mode: `{context['source_mode']}`",
            f"- Prompt version: `{AI_REVIEW_PROMPT_VERSION}`",
            "",
            payload["summary"],
        ],
    )

    finding_lines: list[str] = []
    for idx, item in enumerate(payload["top_findings"], start=1):
        finding_lines.extend(
            [
                f"## Finding {idx}: {item['title']}",
                "",
                f"- Signal strength: `{item['signal_strength']}`",
                f"- Evidence: {item['evidence']}",
                "",
            ]
        )
    _write_markdown(findings_path, "AI Review Top Findings", finding_lines)

    question_lines = [f"- {item}" for item in payload["next_questions"]]
    _write_markdown(questions_path, "AI Review Next Questions", question_lines)

    priority_path.write_text(
        json.dumps(payload["artifact_priority"], ensure_ascii=True, indent=2),
        encoding="utf-8",
    )

    manifest_payload = {
        "provider": provider_config.provider,
        "model": provider_config.model,
        "base_url": provider_config.base_url if provider_config.provider == "ollama" else "",
        "prompt_version": AI_REVIEW_PROMPT_VERSION,
        "demo": context["source_mode"] == "demo",
        "run_ts": run_ts,
        "source_mode": context["source_mode"],
        "input_sources": context["input_sources"],
        "input_evidence_refs": context.get("input_evidence_refs", []),
        "input_artifacts": list(context.get("artifacts", {}).keys()),
        "retrieval_contract_version": context.get("retrieval_contract", {}).get("version", ""),
        "evidence_ref_schema_version": context.get("retrieval_contract", {}).get(
            "evidence_ref_schema_version", ""
        ),
        "safe_rules": [
            "derived-output-first",
            "absolute-paths-redacted",
            "no-raw-db-backup-input",
            "no-live-store-access",
        ],
        "outputs": {
            "triage_summary": str(triage_path),
            "top_findings": str(findings_path),
            "next_questions": str(questions_path),
            "artifact_priority": str(priority_path),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    outputs = {
        "ai_review_dir": str(out_dir),
        "triage_summary": str(triage_path),
        "top_findings": str(findings_path),
        "next_questions": str(questions_path),
        "artifact_priority": str(priority_path),
        "ai_review_manifest": str(manifest_path),
    }
    if root_dir is not None:
        update_review_index_ai_section(root_dir, out_dir)
    return outputs


def run_ai_review(
    *,
    root_dir: Optional[Path],
    out_dir: Path,
    run_ts: Optional[str] = None,
    provider: Optional[str],
    model: Optional[str],
    demo: bool,
    repo_root: Path,
    ollama_base_url: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    allow_cloud: bool = False,
    timeout_sec: int = 120,
) -> dict[str, str]:
    context = build_ai_review_context(root_dir=root_dir, demo=demo, repo_root=repo_root)
    input_evidence_refs = list(context.get("input_evidence_refs", []))
    provider_config = resolve_provider_config(
        provider=provider,
        model=model,
        demo=demo,
        ollama_base_url=ollama_base_url,
        openai_api_key=openai_api_key,
        allow_cloud=allow_cloud,
        timeout_sec=timeout_sec,
    )
    system_prompt, user_prompt = build_ai_review_prompts(context)

    if provider_config.provider == "mock":
        payload = _normalize_payload(
            _generate_mock_payload(context),
            evidence_items=input_evidence_refs,
        )
    elif provider_config.provider == "ollama":
        payload = _generate_ollama_payload(
            config=provider_config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            evidence_items=input_evidence_refs,
        )
    elif provider_config.provider == "openai":
        payload = _generate_openai_payload(
            config=provider_config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            evidence_items=input_evidence_refs,
        )
    else:
        raise RuntimeError(f"Unsupported AI provider: {provider_config.provider}")

    return write_ai_review_outputs(
        out_dir,
        payload,
        provider_config=provider_config,
        context=context,
        root_dir=root_dir,
        run_ts=run_ts or "unknown",
    )


def default_ai_review_dir(root_dir: Path, run_ts: str) -> Path:
    return prefixed_case_dir(root_dir, CASE_DIR_AI_REVIEW, run_ts)


def default_ai_demo_dir() -> Path:
    return Path("./output/AI_Demo_Review")
