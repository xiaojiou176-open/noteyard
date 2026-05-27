from __future__ import annotations

import json
from typing import Any


def register_read_only_surfaces(
    *,
    server,
    registry,
    repo_root,
    retrieval_contract: dict[str, Any],
    read_only,
    demo_resource_map: dict[str, str],
    read_resource_text,
    build_demo_resources,
    summarize_case_root,
    select_case_evidence_payload,
    inspect_case_artifact_payload,
    run_ask_case,
) -> None:
    @server.resource(
        "case://{case_id}/run-manifest",
        name="case_run_manifest",
        mime_type="application/json",
    )
    def case_run_manifest(case_id: str) -> str:
        return read_resource_text(registry.require(case_id).root_dir, "run_manifest")

    @server.resource(
        "case://{case_id}/case-manifest",
        name="case_case_manifest",
        mime_type="application/json",
    )
    def case_case_manifest(case_id: str) -> str:
        return read_resource_text(registry.require(case_id).root_dir, "case_manifest")

    @server.resource(
        "case://{case_id}/pipeline-summary",
        name="case_pipeline_summary",
        mime_type="text/markdown",
    )
    def case_pipeline_summary(case_id: str) -> str:
        return read_resource_text(registry.require(case_id).root_dir, "pipeline_summary")

    @server.resource(
        "case://{case_id}/review-index",
        name="case_review_index",
        mime_type="text/markdown",
    )
    def case_review_index(case_id: str) -> str:
        return read_resource_text(registry.require(case_id).root_dir, "review_index")

    @server.resource(
        "case://{case_id}/verification-summary",
        name="case_verification_summary",
        mime_type="text/plain",
    )
    def case_verification_summary(case_id: str) -> str:
        return read_resource_text(registry.require(case_id).root_dir, "verification_preview")

    @server.resource(
        "case://{case_id}/timeline-summary",
        name="case_timeline_summary",
        mime_type="application/json",
    )
    def case_timeline_summary(case_id: str) -> str:
        return read_resource_text(registry.require(case_id).root_dir, "timeline_summary")

    @server.resource(
        "case://{case_id}/ai-triage-summary",
        name="case_ai_triage_summary",
        mime_type="text/markdown",
    )
    def case_ai_triage_summary(case_id: str) -> str:
        return read_resource_text(registry.require(case_id).root_dir, "ai_triage_summary")

    @server.resource(
        "demo://public-safe/{name}",
        name="demo_public_safe",
        mime_type="text/plain",
    )
    def demo_public_safe(name: str) -> str:
        key = demo_resource_map.get(name)
        if key is None:
            raise ValueError(f"Unknown demo resource: {name}")
        resources = {item.source_id: item for item in build_demo_resources(repo_root)}
        if key not in resources:
            raise ValueError(f"Demo resource is not available: {name}")
        return resources[key].content

    @server.tool(
        name="list_case_roots",
        description="List the allowed case roots that this MCP server can inspect.",
        annotations=read_only,
    )
    def list_case_roots() -> dict[str, Any]:
        cases = []
        for record in registry.list():
            summary = summarize_case_root(record.root_dir, include_ai_review=True)
            cases.append(
                {
                    "case_id": record.case_id,
                    "case_root_name": record.root_dir.name,
                    "resource_count": summary["resource_count"],
                    "resources": summary["resources"],
                    "retrieval_contract_version": summary["retrieval_contract_version"],
                }
            )
        return {
            "cases": cases,
            "retrieval_contract_version": retrieval_contract["version"],
            "primary_retrieval_unit": retrieval_contract["primary_retrieval_unit"],
        }

    @server.tool(
        name="inspect_case_manifest",
        description="Return a structured summary of one case root and its current derived resources.",
        annotations=read_only,
    )
    def inspect_case_manifest(case_id: str) -> dict[str, Any]:
        record = registry.require(case_id)
        summary = summarize_case_root(record.root_dir, include_ai_review=True)
        summary["retrieval_contract"] = retrieval_contract
        return summary

    @server.tool(
        name="select_case_evidence",
        description="Return the shared selector output for one case root and question using the retrieval contract SSOT.",
        annotations=read_only,
    )
    def select_case_evidence_tool(
        case_id: str,
        question: str,
        max_results: int = 6,
    ) -> dict[str, Any]:
        return select_case_evidence_payload(case_id, question, max_results)

    @server.tool(
        name="inspect_case_artifact",
        description="Return one contract-backed derived artifact, including its tier, excerpt, and bounded content.",
        annotations=read_only,
    )
    def inspect_case_artifact(case_id: str, source_id: str) -> dict[str, Any]:
        return inspect_case_artifact_payload(case_id, source_id)

    @server.tool(
        name="inspect_run_manifest",
        description="Return the latest run manifest payload for a case root.",
        annotations=read_only,
    )
    def inspect_run_manifest(case_id: str) -> dict[str, Any]:
        record = registry.require(case_id)
        return json.loads(read_resource_text(record.root_dir, "run_manifest"))

    @server.tool(
        name="ask_case",
        description="Ask an evidence-backed question about one case root using derived review artifacts.",
        annotations=read_only,
    )
    def ask_case(
        case_id: str,
        question: str,
        provider: str | None = None,
        model: str | None = None,
        allow_cloud: bool = False,
    ) -> dict[str, Any]:
        record = registry.require(case_id)
        return run_ask_case(
            root_dir=record.root_dir,
            question=question,
            demo=False,
            repo_root=repo_root,
            provider=provider,
            model=model,
            allow_cloud=allow_cloud,
        )
