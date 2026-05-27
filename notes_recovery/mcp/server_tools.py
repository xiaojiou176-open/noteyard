from __future__ import annotations


def register_bounded_tools(
    *,
    server,
    bounded_write,
    run_verify,
    run_report,
    build_timeline,
    public_safe_export,
) -> None:
    @server.tool(
        name="run_verify",
        description="Run the bounded verify workflow against a case root and return the newest verification outputs.",
        annotations=bounded_write,
    )
    def run_verify_tool(case_id: str, keyword: str, top_n: int = 10, preview_len: int = 300):
        return run_verify(case_id, keyword, top_n, preview_len)

    @server.tool(
        name="run_report",
        description="Run the bounded report workflow against a case root and return the newest report/text-bundle outputs.",
        annotations=bounded_write,
    )
    def run_report_tool(case_id: str, keyword: str | None = None, max_items: int = 50):
        return run_report(case_id, keyword, max_items)

    @server.tool(
        name="build_timeline",
        description="Build the bounded timeline workflow against a case root and return the newest timeline outputs.",
        annotations=bounded_write,
    )
    def build_timeline_tool(
        case_id: str,
        keyword: str | None = None,
        max_notes: int = 200,
        max_events: int = 2000,
        spotlight_max_files: int = 100,
    ):
        return build_timeline(case_id, keyword, max_notes, max_events, spotlight_max_files)

    @server.tool(
        name="public_safe_export",
        description="Create a redacted public-safe bundle for one case root.",
        annotations=bounded_write,
    )
    def public_safe_export_tool(case_id: str, out_dir: str | None = None):
        return public_safe_export(case_id, out_dir)
