from __future__ import annotations

import datetime
import html
import json
import re
from pathlib import Path
from typing import Optional

from notes_recovery.case_contract import (
    CASE_DIR_PLUGINS_OUTPUT,
    CASE_DIR_QUERY_OUTPUT,
    CASE_DIR_RECOVERED_BLOBS,
    case_dir,
)
from notes_recovery.config import PLUGIN_TEXT_EXTENSIONS
from notes_recovery.core.keywords import count_occurrences_for_keywords, count_occurrences_in_file, split_keywords
from notes_recovery.core.scan import collect_prefixed_dirs
from notes_recovery.core.text_bundle import csv_summary
from notes_recovery.io import ensure_dir, iter_files_safe, require_positive_int, safe_read_text


def highlight(text: str, keyword: Optional[str]) -> str:
    escaped = html.escape(text)
    keywords = split_keywords(keyword)
    if not keywords:
        return escaped
    escaped_keywords = [html.escape(item) for item in keywords if item]
    if not escaped_keywords:
        return escaped
    escaped_keywords = sorted(set(escaped_keywords), key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(item) for item in escaped_keywords), re.IGNORECASE)
    return pattern.sub(lambda match: f"<mark>{match.group(0)}</mark>", escaped)


def is_plugin_text_candidate(path: Path) -> bool:
    if path.name == "plugin.log":
        return True
    return path.suffix.lower() in PLUGIN_TEXT_EXTENSIONS


def scan_plugin_outputs(root_dir: Path, keyword: Optional[str], max_items: int) -> dict:
    plugins_root = case_dir(root_dir, CASE_DIR_PLUGINS_OUTPUT)
    sections = []
    heat_items = []
    total_files = 0
    matched_files = 0
    total_occ = 0

    if not plugins_root.exists() or not plugins_root.is_dir():
        return {
            "sections": sections,
            "heat_items": heat_items,
            "total_files": total_files,
            "matched_files": matched_files,
            "total_occ": total_occ,
        }

    for tool_dir in sorted(plugins_root.iterdir()):
        if not tool_dir.is_dir():
            continue
        tool_items = []
        tool_total = 0
        tool_matched = 0
        tool_errors = []
        for file_path in iter_files_safe(tool_dir):
            if not is_plugin_text_candidate(file_path):
                continue
            tool_total += 1
            total_files += 1
            occ = 0
            length = 0
            try:
                if keyword:
                    occ, length = count_occurrences_in_file(file_path, keyword)
                else:
                    length = file_path.stat().st_size
            except Exception as exc:
                tool_errors.append(f"{file_path.name}: {exc}")
                continue
            if keyword and occ > 0:
                tool_matched += 1
                matched_files += 1
                total_occ += occ
            snippet = safe_read_text(file_path, 800)
            heat = occ / max(1.0, length / 1000.0) if keyword else 0.0
            heat_items.append((heat, occ, length, file_path, snippet, tool_dir.name))
            if len(tool_items) < max_items:
                tool_items.append((file_path, snippet, occ, length))
        sections.append(
            (
                tool_dir.name,
                {
                    "total": tool_total,
                    "matched": tool_matched,
                    "items": tool_items,
                    "errors": tool_errors,
                },
            )
        )

    if keyword and heat_items:
        heat_items.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)

    return {
        "sections": sections,
        "heat_items": heat_items,
        "total_files": total_files,
        "matched_files": matched_files,
        "total_occ": total_occ,
    }


def generate_report(root_dir: Path, keyword: Optional[str], out_path: Path, max_items: int) -> None:
    require_positive_int(max_items, "report max item count")
    query_dirs = collect_prefixed_dirs(root_dir, CASE_DIR_QUERY_OUTPUT)
    carve_dirs = collect_prefixed_dirs(root_dir, CASE_DIR_RECOVERED_BLOBS)
    plugin_summary = scan_plugin_outputs(root_dir, keyword, max_items)
    keywords = split_keywords(keyword)

    query_sections = []
    for query_dir in query_dirs:
        query_files = sorted([p for p in query_dir.glob("*.csv") if p.is_file()])
        for csv_file in query_files:
            summary = csv_summary(csv_file, keyword, max_items)
            query_sections.append((f"{query_dir.name}/{csv_file.name}", summary))

    carved_items = []
    carve_total = 0
    carve_occ_total = 0
    carve_heat_items = []
    for carve_dir in carve_dirs:
        manifest_path = carve_dir / "manifest.jsonl"
        if not manifest_path.exists():
            continue
        try:
            with manifest_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        carve_total += 1
                        out_file = Path(record.get("output", ""))
                        snippet = safe_read_text(out_file, 400)
                        occ = count_occurrences_for_keywords(snippet, keywords) if keywords else 0
                        carve_occ_total += occ
                        heat = occ / max(1.0, len(snippet) / 1000.0)
                        carve_heat_items.append((heat, occ, len(snippet), record, snippet, carve_dir.name))
                        if len(carved_items) < max_items:
                            carved_items.append((record, snippet, carve_dir.name))
                    except Exception:
                        continue
        except Exception:
            continue

    if keyword and carve_heat_items:
        carve_heat_items.sort(key=lambda x: x[0], reverse=True)

    now = datetime.datetime.now().isoformat(timespec="seconds")
    keyword_display = ", ".join(keywords) if keywords else "not provided"
    plugin_total = plugin_summary.get("total_files", 0)
    plugin_matched = plugin_summary.get("matched_files", 0)
    plugin_occ = plugin_summary.get("total_occ", 0)
    plugin_heat = (plugin_matched / plugin_total * 100.0) if plugin_total else 0.0
    total_rows = sum(section[1]["total"] for section in query_sections if "error" not in section[1])
    matched_rows = sum(section[1]["matched"] for section in query_sections if "error" not in section[1])
    query_heat = (matched_rows / total_rows * 100.0) if total_rows else 0.0
    query_file_count = len(query_sections)
    carve_dir_count = len(carve_dirs)

    html_parts = [
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "<meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        "<title>Apple Notes Recovery Report</title>",
        "<style>",
        ":root{--bg:#f7f5f2;--card:#ffffff;--text:#1f2937;--muted:#6b7280;--accent:#2563eb;",
        "--accent-2:#0ea5e9;--border:#e5e7eb;--mark:#fff1b6;--soft:#f8fafc}",
        "*{box-sizing:border-box}",
        "body{margin:0;background:var(--bg);color:var(--text);font-family:\"SF Pro Text\",\"Helvetica Neue\",Arial,sans-serif;line-height:1.6}",
        "a{color:var(--accent);text-decoration:none}",
        "a:hover{text-decoration:underline}",
        ".page{max-width:1120px;margin:0 auto;padding:24px}",
        ".hero{background:linear-gradient(135deg,#f8fafc,#eef2ff);border:1px solid var(--border);border-radius:16px;padding:20px 24px;margin-bottom:16px}",
        ".hero-title{font-size:26px;font-weight:700;margin:0}",
        ".hero-sub{color:var(--muted);margin-top:6px}",
        ".meta-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px;margin-top:12px}",
        ".meta-item{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:10px 12px;font-size:13px}",
        ".meta-label{color:var(--muted);font-size:12px;margin-bottom:4px}",
        ".meta-value{word-break:break-all}",
        ".pill{display:inline-block;padding:4px 10px;border-radius:999px;background:#e0f2fe;color:#0c4a6e;font-size:12px;font-weight:600}",
        ".toc{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}",
        ".toc a{background:var(--card);border:1px solid var(--border);border-radius:999px;padding:6px 12px;font-size:13px}",
        ".toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;background:var(--card);",
        "border:1px solid var(--border);border-radius:14px;padding:10px 12px;margin-bottom:16px}",
        ".toolbar input{flex:1;min-width:200px;border:1px solid var(--border);border-radius:10px;",
        "padding:8px 10px;font-size:13px;background:#fff}",
        ".toolbar button{border:1px solid var(--border);background:#f8fafc;border-radius:10px;",
        "padding:8px 10px;font-size:12px;cursor:pointer}",
        ".toolbar button:hover{background:#eef2ff}",
        ".toolbar .hint{color:var(--muted);font-size:12px}",
        ".section{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:16px 18px;margin-bottom:18px}",
        ".section h2{margin:0 0 8px 0}",
        ".kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-top:8px}",
        ".kpi-item{padding:12px;border-radius:12px;border:1px dashed #d1d5db;background:var(--soft)}",
        ".kpi-label{font-size:12px;color:var(--muted)}",
        ".kpi-value{font-size:20px;font-weight:700;margin-top:4px}",
        ".notice{background:#fef3c7;border:1px solid #fcd34d;color:#92400e;padding:10px 12px;border-radius:12px;font-size:13px}",
        "table{width:100%;border-collapse:separate;border-spacing:0;margin-top:10px;font-size:12px}",
        "th,td{padding:8px 10px;border-bottom:1px solid var(--border);vertical-align:top}",
        "th{position:sticky;top:0;background:#f8fafc;text-align:left;font-weight:600}",
        "tbody tr:nth-child(even){background:#fafafa}",
        "tbody tr:hover{background:#f1f5f9}",
        "pre{background:#f8fafc;color:#0f172a;padding:12px;border-radius:10px;border:1px solid var(--border);white-space:pre-wrap;overflow:auto;font-size:12px}",
        "code.path{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;color:#0f172a}",
        "details{border:1px solid var(--border);border-radius:12px;padding:10px 12px;margin:10px 0;background:#fff}",
        "details summary{cursor:pointer;font-weight:600}",
        ".badge{font-size:12px;padding:2px 6px;border-radius:6px;background:#eef2ff;color:#3730a3;margin-left:6px}",
        "mark{background:var(--mark);padding:0 2px;border-radius:3px}",
        "small.muted{color:var(--muted)}",
        ".hidden{display:none !important}",
        "@media (max-width:640px){.page{padding:16px}.hero-title{font-size:22px}table{display:block;overflow:auto}}",
        "</style>",
        "</head><body>",
        "<div class=\"page\">",
        "<header class=\"hero\" id=\"top\">",
        "<div class=\"hero-title\">Apple Notes Recovery Report</div>",
        "<div class=\"hero-sub\">Offline forensic summary for reviewing hits and locating high-value fragments quickly.</div>",
        "<div class=\"meta-grid\">",
        f"<div class=\"meta-item\"><div class=\"meta-label\">Generated At</div><div class=\"meta-value\">{html.escape(now)}</div></div>",
        f"<div class=\"meta-item\"><div class=\"meta-label\">Working Directory</div><div class=\"meta-value\"><code class=\"path\">{html.escape(str(root_dir))}</code></div></div>",
        f"<div class=\"meta-item\"><div class=\"meta-label\">Keyword</div><div class=\"meta-value\">{html.escape(keyword_display)}</div></div>",
        "</div>",
        "</header>",
        "<nav class=\"toc\">",
        "<a href=\"#summary\">Summary</a>",
        "<a href=\"#query\">Query Results</a>",
        "<a href=\"#carve\">Carved Fragments</a>",
        "<a href=\"#plugin\">Plugin Output</a>",
        "</nav>",
        "<div class=\"toolbar\" id=\"filterBar\">",
        "<input id=\"filterBox\" type=\"text\" placeholder=\"Filter keyword (page view only)\">",
        "<button type=\"button\" id=\"expandAll\">Expand all</button>",
        "<button type=\"button\" id=\"collapseAll\">Collapse all</button>",
        "<button type=\"button\" id=\"clearFilter\">Clear filter</button>",
        "<span class=\"hint\">Filtering affects this page only and does not modify original files.</span>",
        "</div>",
    ]

    html_parts.append("<section class=\"section\" id=\"summary\">")
    html_parts.append("<h2>Hit Overview</h2>")
    html_parts.append("<div class=\"notice\">This report shows the Top-N view by default. Use the output directory for the full raw artifacts.</div>")
    html_parts.append("<div class=\"kpi\">")
    html_parts.append(
        f"<div class=\"kpi-item\"><div class=\"kpi-label\">Query Hits</div>"
        f"<div class=\"kpi-value\">{matched_rows}/{total_rows}</div>"
        f"<small class=\"muted\">Density {query_heat:.2f}%</small></div>"
    )
    html_parts.append(
        f"<div class=\"kpi-item\"><div class=\"kpi-label\">Query Files</div>"
        f"<div class=\"kpi-value\">{query_file_count}</div>"
        f"<small class=\"muted\">From {CASE_DIR_QUERY_OUTPUT}</small></div>"
    )
    html_parts.append(
        f"<div class=\"kpi-item\"><div class=\"kpi-label\">Carve Hits</div>"
        f"<div class=\"kpi-value\">{carve_occ_total}</div>"
        f"<small class=\"muted\">Fragment count {carve_total}</small></div>"
    )
    html_parts.append(
        f"<div class=\"kpi-item\"><div class=\"kpi-label\">Carve Directories</div>"
        f"<div class=\"kpi-value\">{carve_dir_count}</div>"
        f"<small class=\"muted\">{CASE_DIR_RECOVERED_BLOBS}*</small></div>"
    )
    html_parts.append(
        f"<div class=\"kpi-item\"><div class=\"kpi-label\">Plugin Hits</div>"
        f"<div class=\"kpi-value\">{plugin_matched}/{plugin_total}</div>"
        f"<small class=\"muted\">Density {plugin_heat:.2f}%, keyword count {plugin_occ}</small></div>"
    )
    html_parts.append(
        f"<div class=\"kpi-item\"><div class=\"kpi-label\">Report Limit</div>"
        f"<div class=\"kpi-value\">Top {max_items}</div>"
        f"<small class=\"muted\">Full content stays in the raw outputs</small></div>"
    )
    html_parts.append("</div>")
    if not keywords:
        html_parts.append("<p><small class=\"muted\">No keyword was provided, so density metrics are informational only.</small></p>")
    html_parts.append("</section>")

    html_parts.append("<section class=\"section\" id=\"query\">")
    html_parts.append("<h2>Query Results</h2>")
    if not query_sections:
        html_parts.append("<p>No query output was found.</p>")
    for idx, (name, summary) in enumerate(query_sections):
        open_attr = " open" if idx < 1 else ""
        html_parts.append(f"<details{open_attr}>")
        html_parts.append(f"<summary>{html.escape(name)}")
        if "error" not in summary:
            heat = (summary["matched"] / summary["total"] * 100.0) if summary["total"] else 0.0
            html_parts.append(f"<span class=\"badge\">Density {heat:.2f}%</span>")
        html_parts.append("</summary>")
        if "error" in summary:
            html_parts.append(f"<p>Error: {html.escape(summary['error'])}</p>")
            html_parts.append("</details>")
            continue
        heat = (summary["matched"] / summary["total"] * 100.0) if summary["total"] else 0.0
        html_parts.append(
            f"<p>Total rows: {summary['total']} | Matched rows: {summary['matched']} | Density: {heat:.2f}%</p>"
        )
        header = summary["header"]
        preview = summary["preview"]
        if header and preview:
            html_parts.append("<table><thead><tr>")
            for col in header:
                html_parts.append(f"<th>{html.escape(col)}</th>")
            html_parts.append("</tr></thead><tbody>")
            for row in preview:
                html_parts.append("<tr>")
                for cell in row:
                    html_parts.append(f"<td>{highlight(str(cell), keyword)}</td>")
                html_parts.append("</tr>")
            html_parts.append("</tbody></table>")
        else:
            html_parts.append("<p>No preview rows are available.</p>")
        html_parts.append("</details>")
    html_parts.append("</section>")

    html_parts.append("<section class=\"section\" id=\"carve\">")
    html_parts.append("<h2>Carved Fragments</h2>")
    html_parts.append(f"<p>Total fragments recorded in manifests: {carve_total}</p>")
    if not carved_items:
        html_parts.append("<p>No carve results were found, or the manifest is missing.</p>")
    for idx, (record, snippet, carve_label) in enumerate(carved_items):
        out_file = record.get("output", "")
        open_attr = " open" if idx < 1 else ""
        html_parts.append(f"<details{open_attr}>")
        html_parts.append(
            f"<summary>{html.escape(carve_label)} - {html.escape(out_file)}"
            f"<span class=\"badge\">Fragment</span></summary>"
        )
        html_parts.append("<pre>")
        html_parts.append(highlight(snippet, keyword))
        html_parts.append("</pre>")
        html_parts.append("</details>")

    if keywords and carve_heat_items:
        html_parts.append("<h3>Carve Density Ranking (Top)</h3>")
        html_parts.append("<table><thead><tr>")
        html_parts.append("<th>Density Score</th><th>Keyword Count</th><th>Fragment Length</th><th>File</th>")
        html_parts.append("</tr></thead><tbody>")
        for heat, occ, length, record, _snippet, carve_label in carve_heat_items[:max_items]:
            label = f"{carve_label} - {Path(record.get('output', '')).name}"
            html_parts.append("<tr>")
            html_parts.append(f"<td>{heat:.2f}</td>")
            html_parts.append(f"<td>{occ}</td>")
            html_parts.append(f"<td>{length}</td>")
            html_parts.append(f"<td>{html.escape(label)}</td>")
            html_parts.append("</tr>")
        html_parts.append("</tbody></table>")
    html_parts.append("</section>")

    html_parts.append("<section class=\"section\" id=\"plugin\">")
    html_parts.append("<h2>Plugin Output</h2>")
    if not plugin_summary.get("sections"):
        html_parts.append("<p>No plugin output was found.</p>")
    for idx, (tool_name, payload) in enumerate(plugin_summary.get("sections", [])):
        open_attr = " open" if idx < 1 else ""
        html_parts.append(f"<details{open_attr}>")
        html_parts.append(
            f"<summary>{html.escape(tool_name)}"
            f"<span class=\"badge\">{payload.get('matched', 0)}/{payload.get('total', 0)}</span></summary>"
        )
        if payload.get("errors"):
            html_parts.append("<ul>")
            for item in payload["errors"]:
                html_parts.append(f"<li>{html.escape(item)}</li>")
            html_parts.append("</ul>")
        items = payload.get("items", [])
        if items:
            html_parts.append("<table><thead><tr>")
            html_parts.append("<th>File</th><th>Keyword Count</th><th>Length</th><th>Preview</th>")
            html_parts.append("</tr></thead><tbody>")
            for file_path, snippet, occ, length in items:
                html_parts.append("<tr>")
                html_parts.append(f"<td>{html.escape(str(file_path.name))}</td>")
                html_parts.append(f"<td>{occ}</td>")
                html_parts.append(f"<td>{length}</td>")
                html_parts.append(f"<td>{highlight(snippet, keyword)}</td>")
                html_parts.append("</tr>")
            html_parts.append("</tbody></table>")
        else:
            html_parts.append("<p>No displayable content was found.</p>")
        html_parts.append("</details>")

    if keywords and plugin_summary.get("heat_items"):
        html_parts.append("<h3>Plugin Hit Density Ranking (Top)</h3>")
        html_parts.append("<table><thead><tr>")
        html_parts.append("<th>Density Score</th><th>Keyword Count</th><th>Length</th><th>File</th>")
        html_parts.append("</tr></thead><tbody>")
        for heat, occ, length, file_path, _snippet, tool_name in plugin_summary["heat_items"][:max_items]:
            label = f"{tool_name} - {file_path.name}"
            html_parts.append("<tr>")
            html_parts.append(f"<td>{heat:.2f}</td>")
            html_parts.append(f"<td>{occ}</td>")
            html_parts.append(f"<td>{length}</td>")
            html_parts.append(f"<td>{html.escape(label)}</td>")
            html_parts.append("</tr>")
        html_parts.append("</tbody></table>")

    html_parts.append("<p><a href=\"#top\">Back to top</a></p>")
    html_parts.append("</section>")
    html_parts.append("<script>")
    html_parts.append("(function(){")
    html_parts.append("const filterBox=document.getElementById('filterBox');")
    html_parts.append("const clearBtn=document.getElementById('clearFilter');")
    html_parts.append("const expandBtn=document.getElementById('expandAll');")
    html_parts.append("const collapseBtn=document.getElementById('collapseAll');")
    html_parts.append("const details=Array.from(document.querySelectorAll('details'));")
    html_parts.append("const tables=Array.from(document.querySelectorAll('table'));")
    html_parts.append("const sections=Array.from(document.querySelectorAll('.section'));")
    html_parts.append("function setAll(open){details.forEach(d=>{d.open=open;});}")
    html_parts.append("function rowMatch(row,q){return row.textContent.toLowerCase().includes(q);}")
    html_parts.append("function applyFilter(){const q=filterBox.value.trim().toLowerCase();")
    html_parts.append("details.forEach(d=>{if(!q){d.classList.remove('hidden');return;}")
    html_parts.append("const text=d.textContent.toLowerCase();d.classList.toggle('hidden',!text.includes(q));});")
    html_parts.append("tables.forEach(t=>{const rows=Array.from(t.querySelectorAll('tbody tr'));")
    html_parts.append("if(!rows.length){return;}if(!q){rows.forEach(r=>r.classList.remove('hidden'));t.classList.remove('hidden');return;}")
    html_parts.append("rows.forEach(r=>r.classList.toggle('hidden',!rowMatch(r,q)));")
    html_parts.append("const anyVisible=rows.some(r=>!r.classList.contains('hidden'));t.classList.toggle('hidden',!anyVisible);});")
    html_parts.append("sections.forEach(s=>{if(!q){s.classList.remove('hidden');return;}")
    html_parts.append("const text=s.textContent.toLowerCase();s.classList.toggle('hidden',!text.includes(q));});")
    html_parts.append("}")
    html_parts.append("filterBox.addEventListener('input', applyFilter);")
    html_parts.append("clearBtn.addEventListener('click', ()=>{filterBox.value='';applyFilter();});")
    html_parts.append("expandBtn.addEventListener('click', ()=>setAll(true));")
    html_parts.append("collapseBtn.addEventListener('click', ()=>setAll(false));")
    html_parts.append("})();")
    html_parts.append("</script>")
    html_parts.append("</div></body></html>")

    ensure_dir(out_path.parent)
    try:
        with out_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(html_parts))
    except Exception as exc:
        raise RuntimeError(f"Failed to write report: {out_path} -> {exc}")
