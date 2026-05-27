from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from notes_recovery.mcp import server as mcp_server


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_case_root(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    root.mkdir()
    _write(root / "review_index.md", "# Review Index\n\n- Start with verification.\n")
    _write(root / "run_manifest_20260331_000000.json", json.dumps({"run_ts": "20260331_000000", "root_dir": str(root)}, ensure_ascii=True))
    _write(root / "case_manifest_20260331_000000.json", json.dumps({"root_dir": str(root), "stage_outputs": []}, ensure_ascii=True))
    _write(root / "Meta" / "pipeline_summary_20260331_000000.md", "# Pipeline Summary\n\n- OK\n")
    _write(root / "Query_Output_20260331" / "sample.csv", "col1,col2\norchard lane,meeting\n")
    _write(root / "AI_Review_20260331" / "triage_summary.md", "# AI Review Triage Summary\n\n- Start with verification.\n")
    return root


def _json_from_tool(result) -> dict:
    assert result.content
    return json.loads(result.content[0].text)


def test_mcp_help_does_not_require_optional_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called():
        raise AssertionError("optional MCP runtime should not be loaded for --help")

    monkeypatch.setattr(mcp_server, "_load_mcp_runtime", fail_if_called)

    with pytest.raises(SystemExit) as exc:
        mcp_server.main(["--help"])

    assert exc.value.code == 0


def test_mcp_runtime_emits_install_hint_when_dependency_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def raise_missing():
        raise SystemExit(mcp_server.MCP_DEPENDENCY_HELP)

    monkeypatch.setattr(mcp_server, "_load_mcp_runtime", raise_missing)

    with pytest.raises(SystemExit) as exc:
        mcp_server.main(["--case-dir", str(tmp_path)])

    assert str(exc.value) == mcp_server.MCP_DEPENDENCY_HELP


def test_mcp_server_lists_resources_and_runs_verify(tmp_path: Path) -> None:
    case_root = _build_case_root(tmp_path)

    async def scenario() -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "notes_recovery.mcp.server", "--case-dir", str(case_root)],
            cwd=str(Path.cwd()),
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tools = await session.list_tools()
                tool_names = {tool.name for tool in tools.tools}
                assert {
                    "list_case_roots",
                    "inspect_case_manifest",
                    "inspect_case_artifact",
                    "select_case_evidence",
                    "run_verify",
                    "ask_case",
                }.issubset(tool_names)

                templates = await session.list_resource_templates()
                template_uris = {item.uriTemplate for item in templates.resourceTemplates}
                assert "case://{case_id}/run-manifest" in template_uris
                assert "case://{case_id}/review-index" in template_uris

                listed = await session.call_tool("list_case_roots")
                listed_payload = _json_from_tool(listed)
                assert len(listed_payload["cases"]) == 1
                assert listed_payload["retrieval_contract_version"] == "2026-04-02.v1"
                case_id = listed_payload["cases"][0]["case_id"]

                inspected = await session.call_tool("inspect_case_manifest", {"case_id": case_id})
                inspected_payload = _json_from_tool(inspected)
                assert inspected_payload["primary_retrieval_unit"] == "one-case-root-at-a-time"
                assert inspected_payload["retrieval_contract"]["version"] == "2026-04-02.v1"

                artifact = await session.call_tool(
                    "inspect_case_artifact",
                    {"case_id": case_id, "source_id": "review_index"},
                )
                artifact_payload = _json_from_tool(artifact)
                assert artifact_payload["source_id"] == "review_index"
                assert artifact_payload["tier"] == "tier_a_anchor"
                assert artifact_payload["retrieval_contract_version"] == "2026-04-02.v1"
                assert "Review Index" in artifact_payload["content"]

                selected = await session.call_tool(
                    "select_case_evidence",
                    {"case_id": case_id, "question": "orchard lane", "max_results": 4},
                )
                selected_payload = _json_from_tool(selected)
                assert selected_payload["retrieval_contract_version"] == "2026-04-02.v1"
                assert selected_payload["primary_retrieval_unit"] == "one-case-root-at-a-time"
                assert selected_payload["evidence_ref_schema_version"] == "2026-04-02.v1"
                assert selected_payload["evidence_refs"]
                assert all(item["selection_reason"] for item in selected_payload["evidence_refs"])
                review_index_ref = next(
                    item for item in selected_payload["evidence_refs"] if item["source_id"] == "review_index"
                )
                assert "fallback" in review_index_ref["selection_reason"]

                resource = await session.read_resource(f"case://{case_id}/review-index")
                assert resource.contents
                assert "Review Index" in resource.contents[0].text

                verify_result = await session.call_tool(
                    "run_verify",
                    {"case_id": case_id, "keyword": "orchard lane", "top_n": 5, "preview_len": 120},
                )
                verify_payload = _json_from_tool(verify_result)
                assert verify_payload["exit_code"] == 0
                assert any(path.startswith("Verification_") for path in verify_payload["resources"].values())

    asyncio.run(scenario())
