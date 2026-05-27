#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive forensics dashboard (Streamlit).
Usage: forensics-dashboard.
"""

from __future__ import annotations

import html
import json
import datetime
from pathlib import Path
from typing import Any, Optional

from notes_recovery.config import DEFAULT_OUTPUT_ROOT
from notes_recovery.io import safe_read_text
from notes_recovery.services.case_diff import (
    build_case_diff_payload,
    build_case_diff_summary,
)
from notes_recovery.services.case_protocol import (
    build_case_resources,
    build_evidence_ref,
    build_case_resource_lookup,
    discover_case_roots,
    select_case_evidence,
    summarize_case_root,
)
from notes_recovery.services.timeline import find_latest_file as find_latest_file_recursive


def _try_import(module: str):
    try:
        return __import__(module)
    except Exception:
        return None




st = None
pd = None
px = None
plotly_graph_objects = None
networkx = None

DASHBOARD_THEME_CSS = """
<style>
  :root {
    --nsl-bg: #081019;
    --nsl-bg-deep: #0d1722;
    --nsl-panel: rgba(13, 23, 34, 0.72);
    --nsl-panel-strong: rgba(14, 27, 40, 0.9);
    --nsl-line: rgba(255, 255, 255, 0.08);
    --nsl-line-strong: rgba(255, 255, 255, 0.14);
    --nsl-ink: #f4f7fb;
    --nsl-muted: #b8c4d1;
    --nsl-accent: #7fd5ff;
    --nsl-accent-strong: #45b8ff;
    --nsl-success: #8fe3b2;
    --nsl-shadow: 0 22px 60px rgba(0, 0, 0, 0.24);
  }

  .stApp {
    background:
      radial-gradient(circle at 0% 0%, rgba(69, 184, 255, 0.18), transparent 28%),
      radial-gradient(circle at 100% 12%, rgba(127, 213, 255, 0.12), transparent 24%),
      linear-gradient(180deg, var(--nsl-bg) 0%, var(--nsl-bg-deep) 100%);
    color: var(--nsl-ink);
  }

  [data-testid="stHeader"] {
    background: rgba(8, 16, 25, 0.72);
  }

  [data-testid="stSidebar"] {
    background:
      linear-gradient(180deg, rgba(7, 15, 24, 0.92), rgba(11, 21, 33, 0.92));
    border-right: 1px solid var(--nsl-line);
  }

  [data-testid="stSidebar"] * {
    color: var(--nsl-ink);
  }

  [data-testid="stSidebar"] .stTextInput > div > div,
  [data-testid="stSidebar"] .stCheckbox {
    background: transparent;
  }

  [data-testid="stSidebar"] input {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--nsl-line);
    border-radius: 14px;
  }

  [data-testid="stAppViewContainer"] {
    color: var(--nsl-ink);
  }

  .block-container {
    padding-top: 2.1rem;
    padding-bottom: 3rem;
  }

  h1, h2, h3, h4, h5, h6 {
    color: var(--nsl-ink);
    letter-spacing: -0.02em;
  }

  p, li, label, .stCaption, .stMarkdown, .stText {
    color: var(--nsl-muted);
  }

  div[data-testid="stMetric"] {
    border: 1px solid var(--nsl-line);
    border-radius: 18px;
    padding: 0.9rem 1rem;
    background: rgba(255, 255, 255, 0.04);
    box-shadow: var(--nsl-shadow);
  }

  div[data-testid="stMetricLabel"] {
    color: var(--nsl-muted);
  }

  div[data-testid="stMetricValue"] {
    color: var(--nsl-ink);
  }

  .stTabs [data-baseweb="tab-list"] {
    gap: 0.6rem;
    padding-bottom: 0.5rem;
  }

  .stTabs [data-baseweb="tab"] {
    height: auto;
    padding: 0.65rem 1rem;
    border-radius: 999px;
    border: 1px solid var(--nsl-line);
    background: rgba(255, 255, 255, 0.03);
    color: var(--nsl-muted);
  }

  .stTabs [aria-selected="true"] {
    background: rgba(69, 184, 255, 0.14);
    border-color: rgba(127, 213, 255, 0.28);
    color: var(--nsl-ink);
  }

  .stTabs [data-baseweb="tab-highlight"] {
    background: transparent;
  }

  [data-testid="stExpander"] {
    border: 1px solid var(--nsl-line);
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.03);
    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.14);
    overflow: hidden;
  }

  [data-testid="stExpander"] details summary {
    padding: 0.2rem 0.35rem;
    color: var(--nsl-ink);
  }

  [data-testid="stExpander"] details summary p {
    color: var(--nsl-ink);
    font-weight: 700;
  }

  .stCodeBlock,
  pre {
    border-radius: 18px;
  }

  .stDataFrame, div[data-testid="stDataFrame"], div[data-testid="stTable"] {
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid var(--nsl-line);
  }

  .nsl-hero,
  .nsl-section-head {
    position: relative;
    overflow: hidden;
    border: 1px solid var(--nsl-line);
    border-radius: 28px;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0)),
      rgba(12, 23, 35, 0.7);
    box-shadow: var(--nsl-shadow);
  }

  .nsl-hero::after,
  .nsl-section-head::after {
    content: "";
    position: absolute;
    right: -120px;
    top: -120px;
    width: 320px;
    height: 320px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(127, 213, 255, 0.14) 0%, rgba(127, 213, 255, 0) 68%);
    pointer-events: none;
  }

  .nsl-hero {
    display: grid;
    gap: 1.25rem;
    margin: 0 0 1.3rem;
    padding: 1.4rem;
  }

  .nsl-hero-kicker,
  .nsl-section-kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    width: fit-content;
    min-height: 32px;
    padding: 0 0.75rem;
    border-radius: 999px;
    background: rgba(127, 213, 255, 0.12);
    color: var(--nsl-accent);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .nsl-hero h2,
  .nsl-section-head h2 {
    margin: 0.7rem 0 0.55rem;
    font-size: clamp(1.85rem, 4vw, 3.2rem);
    line-height: 1.02;
  }

  .nsl-hero p,
  .nsl-section-head p {
    margin: 0;
    max-width: 72ch;
    color: var(--nsl-muted);
  }

  .nsl-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    margin-top: 1rem;
  }

  .nsl-badge,
  .nsl-meta-chip {
    display: inline-flex;
    align-items: center;
    min-height: 36px;
    padding: 0 0.9rem;
    border-radius: 999px;
    border: 1px solid var(--nsl-line);
    background: rgba(255, 255, 255, 0.04);
    color: var(--nsl-ink);
    font-size: 0.92rem;
  }

  .nsl-meta {
    display: grid;
    gap: 0.65rem;
    margin-top: 0.5rem;
  }

  .nsl-meta code {
    color: var(--nsl-ink);
    word-break: break-word;
  }

  .nsl-section-head {
    margin: 0.25rem 0 1rem;
    padding: 1.15rem 1.25rem;
  }

  .nsl-step-card {
    position: relative;
    min-height: 100%;
    padding: 1rem 1rem 1.05rem;
    border: 1px solid var(--nsl-line);
    border-radius: 20px;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0)),
      rgba(255, 255, 255, 0.03);
    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.14);
  }

  .nsl-step-card::before {
    content: "";
    display: block;
    width: 58px;
    height: 4px;
    margin-bottom: 0.8rem;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--nsl-accent-strong), rgba(69, 184, 255, 0.18));
  }

  .nsl-step-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    margin-bottom: 0.8rem;
    background: rgba(127, 213, 255, 0.12);
    border: 1px solid rgba(127, 213, 255, 0.2);
    color: var(--nsl-accent);
    font-size: 0.88rem;
    font-weight: 700;
  }

  .nsl-step-title {
    margin: 0 0 0.45rem;
    color: var(--nsl-ink);
    font-size: 1rem;
    font-weight: 700;
    line-height: 1.35;
  }

  .nsl-step-detail {
    margin: 0;
    color: var(--nsl-muted);
    font-size: 0.95rem;
    line-height: 1.55;
  }

  @media (prefers-reduced-motion: reduce) {
    * {
      transition: none !important;
      animation: none !important;
    }
  }
</style>
"""


# =============================================================================
# Helpers
# =============================================================================


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except Exception:
        return 0.0


def inject_dashboard_theme() -> None:
    if st is None:
        return
    st.markdown(DASHBOARD_THEME_CSS, unsafe_allow_html=True)


def render_dashboard_hero(
    review_root: Path,
    case_roots: list[Path],
    case_summary: dict[str, Any],
) -> None:
    if st is None:
        return
    ai_ready = "AI review layer ready" if "ai_triage_summary" in case_summary["resources"] else "AI review layer missing"
    compare_ready = "Compare-ready" if len(case_roots) > 1 else "Single-case focus"
    hero_html = f"""
<section class="nsl-hero">
  <div>
    <span class="nsl-hero-kicker">Local-only review cockpit</span>
    <h2>Start with the proof spine, then peel deeper only when the evidence demands it.</h2>
    <p>
      Treat this cockpit like a triage desk. The first tab tells you what to open first,
      the later tabs hold the heavier forensic surfaces, and nothing here needs to mutate
      the underlying case root.
    </p>
    <div class="nsl-badges">
      <span class="nsl-badge">{len(case_roots)} case root(s) discovered</span>
      <span class="nsl-badge">{case_summary["resource_count"]} derived resource(s)</span>
      <span class="nsl-badge">{html.escape(ai_ready)}</span>
      <span class="nsl-badge">{html.escape(compare_ready)}</span>
    </div>
  </div>
  <div class="nsl-meta">
    <span class="nsl-meta-chip">Review root: <code>{html.escape(str(review_root))}</code></span>
    <span class="nsl-meta-chip">Cognitive load policy: overview first, advanced evidence later</span>
  </div>
</section>
"""
    st.markdown(hero_html, unsafe_allow_html=True)


def render_dashboard_section_header(kicker: str, title: str, detail: str) -> None:
    if st is None:
        return
    section_html = f"""
<section class="nsl-section-head">
  <span class="nsl-section-kicker">{html.escape(kicker)}</span>
  <h2>{html.escape(title)}</h2>
  <p>{html.escape(detail)}</p>
</section>
"""
    st.markdown(section_html, unsafe_allow_html=True)


def render_start_here_cards(steps: list[dict[str, str]]) -> None:
    if st is None or not steps:
        return
    columns = st.columns(min(3, len(steps)))
    for idx, step in enumerate(steps[:3]):
        card_html = f"""
<article class="nsl-step-card">
  <span class="nsl-step-index">{idx + 1}</span>
  <h3 class="nsl-step-title">{html.escape(step["title"])}</h3>
  <p class="nsl-step-detail">{html.escape(step["detail"])}</p>
</article>
"""
        with columns[idx]:
            st.markdown(card_html, unsafe_allow_html=True)


def find_latest_file(root_dir: Path, pattern: str, recursive: bool) -> Optional[Path]:
    if not root_dir.exists():
        return None
    if recursive:
        return find_latest_file_recursive(root_dir, pattern)
    candidates = list(root_dir.glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=_safe_mtime, default=None)


def load_json(path: Path) -> Optional[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_csv(path: Path):
    if pd is None:
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def load_review_csv(path: Path):
    if pd is None:
        return None
    columns = [
        "stitched_id",
        "verdict",
        "note",
        "updated_at",
        "sources",
        "cluster_id",
        "length",
        "score",
        "confidence",
        "md_path",
        "txt_path",
        "html_path",
    ]
    if not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_csv(path)
        missing = [col for col in columns if col not in df.columns]
        for col in missing:
            df[col] = ""
        return df
    except Exception:
        return pd.DataFrame(columns=columns)


def save_review_csv(path: Path, df) -> bool:
    if pd is None:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        return True
    except Exception:
        return False


def upsert_review_row(df, row: dict[str, Any]):
    if pd is None or df is None:
        return df
    stitched_id = row.get("stitched_id")
    if stitched_id is None:
        return df
    try:
        stitched_id_int = int(stitched_id)
    except Exception:
        stitched_id_int = stitched_id
    if "stitched_id" in df.columns:
        mask = df["stitched_id"] == stitched_id_int
        if mask.any():
            for key, value in row.items():
                df.loc[mask, key] = value
            return df
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def build_fragment_lookup(manifest_path: Path) -> dict[int, dict[str, Any]]:
    df = load_csv(manifest_path)
    if df is None or df.empty:
        return {}
    lookup: dict[int, dict[str, Any]] = {}
    for _idx, row in df.iterrows():
        frag_id_raw = row.get("id", row.get("fragment_id", ""))
        try:
            frag_id = int(frag_id_raw)
        except Exception:
            continue
        lookup[frag_id] = {str(col): row.get(col, "") for col in df.columns}
    return lookup


def extract_source_path(source_detail: str) -> Optional[Path]:
    if not source_detail:
        return None
    path_str = source_detail.split("::", 1)[0].strip()
    if not path_str:
        return None
    path = Path(path_str).expanduser()
    if path.exists():
        return path
    return None


def resolve_review_case_roots(root_dir: Path, recursive_scan: bool) -> list[Path]:
    search_roots = [root_dir] if recursive_scan else []
    case_roots = discover_case_roots(case_dirs=[root_dir], search_roots=search_roots)
    return case_roots or [root_dir]


def resource_absolute_path(case_root: Path, rel_path: str) -> Optional[Path]:
    if not rel_path or rel_path == "(missing)":
        return None
    path = (case_root / rel_path).resolve()
    if path.exists():
        return path
    return None


def render_resource_link(st_module, label: str, case_root: Path, rel_path: str) -> None:
    path = resource_absolute_path(case_root, rel_path)
    if path is None:
        st_module.markdown(f"- {label}: (missing)")
        return
    st_module.markdown(f"- [{label}]({path.as_uri()})")
    st_module.code(str(path))


def build_review_workspace_snapshot(
    root_dir: Path,
    question: str,
) -> Optional[dict[str, Any]]:
    if not root_dir.exists():
        return None
    try:
        normalized_question = question.strip() or "What should I inspect first?"
        resources = build_case_resources(root_dir, include_ai_review=True)
        evidence = select_case_evidence(resources, normalized_question, max_results=6)
        return {
            "question": normalized_question,
            "summary": summarize_case_root(root_dir, include_ai_review=True),
            "evidence_refs": [build_evidence_ref(item) for item in evidence],
        }
    except Exception:
        return None


def build_start_here_steps(
    case_summary: dict[str, Any],
    *,
    has_operator_brief: bool,
    has_compare_candidates: bool,
) -> list[dict[str, str]]:
    resources = case_summary.get("resources", {})
    steps: list[dict[str, str]] = []

    if resources.get("review_index"):
        steps.append(
            {
                "title": "Open the review index first",
                "detail": "Use the review index to understand the workflow order before drilling into narrower artifacts.",
            }
        )
    if resources.get("verification_preview"):
        steps.append(
            {
                "title": "Check the verification preview next",
                "detail": "This is the fastest high-signal surface for ranked hits and quick sanity checks.",
            }
        )
    if has_operator_brief:
        steps.append(
            {
                "title": "Read the operator brief for boundary context",
                "detail": "Use the brief to confirm why the case stayed copy-first and how to keep the review share-safe.",
            }
        )
    else:
        steps.append(
            {
                "title": "Use the evidence ladder to choose the next artifact",
                "detail": "Ask one bounded question and let the cockpit rank which derived artifacts deserve attention next.",
            }
        )
    if resources.get("ai_triage_summary"):
        steps.append(
            {
                "title": "Use AI quick view as a summary layer, not as ground truth",
                "detail": "Treat AI triage as a shortcut after you understand the review spine and evidence order.",
            }
        )
    if has_compare_candidates:
        steps.append(
            {
                "title": "Only compare after the current case makes sense",
                "detail": "Case diff is strongest when you already understand the current root and need to explain drift across runs.",
            }
        )
    return steps


def run_dashboard() -> None:
    global st, pd, px, plotly_graph_objects, networkx
    st = _try_import("streamlit")
    if st is None:
        raise SystemExit("Streamlit is required: pip install streamlit plotly networkx pandas")
    pd = _try_import("pandas")
    networkx = _try_import("networkx")
    try:
        import plotly.express as px  # type: ignore
        import plotly.graph_objects as plotly_graph_objects  # type: ignore
    except Exception:
        px = None
        plotly_graph_objects = None
    st.set_page_config(page_title="Noteyard review cockpit", layout="wide")
    inject_dashboard_theme()

    st.title("Noteyard review cockpit")

    with st.sidebar:
        st.header("Data source")
        root_dir_str = st.text_input("Output root", str(DEFAULT_OUTPUT_ROOT))
        recursive_scan = st.checkbox("Scan child directories recursively", value=True)
        st.caption("Defaults to the CLI output root, but you can point it at a specific exported case directory.")

    root_dir = Path(root_dir_str).expanduser().resolve()

    if not root_dir.exists():
        st.error(f"Path does not exist: {root_dir}")
        st.stop()

    case_roots = resolve_review_case_roots(root_dir, recursive_scan)
    review_root = case_roots[0].resolve()

    st.subheader("Review cockpit")
    st.caption(
        "Local-only richer review surface for case-root selection, derived-resource inspection, AI quick view, and bounded case comparison."
    )
    if len(case_roots) > 1:
        selected_case = st.selectbox(
            "Case root",
            [str(path) for path in case_roots],
            index=0,
        )
        review_root = Path(selected_case).expanduser().resolve()
    st.caption(f"Review root: {review_root}")

    case_summary = summarize_case_root(review_root, include_ai_review=True)
    resource_lookup = build_case_resource_lookup(review_root, include_ai_review=True)
    resource_items = case_summary["resource_items"]
    operator_brief_path = find_latest_file(review_root, "*operator*brief*.md", recursive_scan)
    compare_candidates = [path for path in case_roots if path.resolve() != review_root]
    start_here_steps = build_start_here_steps(
        case_summary,
        has_operator_brief=operator_brief_path is not None,
        has_compare_candidates=bool(compare_candidates),
    )
    render_dashboard_hero(review_root, case_roots, case_summary)

    overview_tab, timeline_tab, spotlight_tab, stitched_tab = st.tabs(
        ["Start here", "Timeline", "Spotlight", "Stitched review"]
    )

    with overview_tab:
        render_dashboard_section_header(
            "Start here",
            "Open the proof spine first, not the deepest forensic view.",
            "This tab keeps the first decision easy: confirm the case root, inspect the core derived resources, then let the evidence ladder or AI summary tell you what deserves the next click.",
        )
        metrics = st.columns(4)
        metrics[0].metric("Discovered case roots", len(case_roots))
        metrics[1].metric("Derived resources", case_summary["resource_count"])
        metrics[2].metric(
            "AI review surface",
            "yes" if "ai_triage_summary" in case_summary["resources"] else "no",
        )
        metrics[3].metric(
            "Compare-ready",
            "yes" if len(case_roots) > 1 else "no",
        )

        st.markdown("**Start here**")
        render_start_here_cards(start_here_steps)
        if len(start_here_steps) > 3:
            for idx, step in enumerate(start_here_steps[3:], start=4):
                st.markdown(f"{idx}. **{step['title']}**")
                st.markdown(f"   - {step['detail']}")

        st.markdown("**Core review surfaces**")
        for source_id, label in (
            ("review_index", "Review index"),
            ("run_manifest", "Run manifest"),
            ("case_manifest", "Case manifest"),
            ("pipeline_summary", "Pipeline summary"),
            ("verification_preview", "Verification preview"),
            ("report_excerpt", "HTML report"),
            ("text_bundle_inventory", "Text bundle inventory"),
            ("ai_triage_summary", "AI triage summary"),
            ("ai_top_findings", "AI top findings"),
            ("ai_next_questions", "AI next questions"),
        ):
            rel_path = case_summary["resources"].get(source_id, "(missing)")
            render_resource_link(st, label, review_root, rel_path)
        if operator_brief_path is not None:
            st.markdown("**Operator brief**")
            st.markdown(f"- [Operator brief]({operator_brief_path.as_uri()})")
            st.code(str(operator_brief_path))
        else:
            st.markdown("**Operator brief**")
            st.caption("No operator brief artifact was found for this case root yet. Stay anchored on the review index and verification preview.")

        if pd is not None and resource_items:
            with st.expander("Derived resource inventory", expanded=False):
                st.dataframe(pd.DataFrame(resource_items), use_container_width=True, height=220)

        review_index_resource = resource_lookup.get("review_index")
        if review_index_resource is not None:
            with st.expander("Review index preview", expanded=True):
                st.code(review_index_resource.content[:6000], language="markdown")

        pipeline_summary_resource = resource_lookup.get("pipeline_summary")
        if pipeline_summary_resource is not None:
            with st.expander("Pipeline summary preview", expanded=False):
                st.code(pipeline_summary_resource.content[:4000], language="markdown")

        verification_preview_resource = resource_lookup.get("verification_preview")
        if verification_preview_resource is not None:
            with st.expander("Verification preview", expanded=True):
                st.code(verification_preview_resource.content[:4000], language="text")

        workspace_snapshot = build_review_workspace_snapshot(
            review_root,
            st.text_input("Evidence question (derived artifacts only)", "What should I inspect first?"),
        )
        if workspace_snapshot is not None and workspace_snapshot["evidence_refs"]:
            st.markdown("**Evidence ladder**")
            st.caption("Use this before the AI summary when you want the cockpit to explain why a specific artifact deserves your next click.")
            if pd is not None:
                st.dataframe(
                    pd.DataFrame(workspace_snapshot["evidence_refs"])[
                        ["source_id", "artifact", "kind", "score", "selection_reason"]
                    ],
                    use_container_width=True,
                    height=220,
                )
            for item in workspace_snapshot["evidence_refs"][:3]:
                st.markdown(f"**{item['artifact']}**")
                st.markdown(f"- Source: `{item['source_id']}`")
                st.markdown(f"- Why it matters: {item['selection_reason']}")
                if item.get("excerpt"):
                    st.code(item["excerpt"], language="text")

        ai_triage = resource_lookup.get("ai_triage_summary")
        ai_findings = resource_lookup.get("ai_top_findings")
        ai_questions = resource_lookup.get("ai_next_questions")
        if ai_triage or ai_findings or ai_questions:
            with st.expander("AI review quick view", expanded=False):
                st.caption("Treat AI as a summary layer after the review spine and evidence ladder, not as a replacement for them.")
                if ai_triage is not None:
                    st.code(ai_triage.content[:3000], language="markdown")
                if ai_findings is not None:
                    st.code(ai_findings.content[:3000], language="markdown")
                if ai_questions is not None:
                    st.code(ai_questions.content[:3000], language="markdown")

        artifact_priority_path = find_latest_file(review_root, "artifact_priority.json", recursive_scan)
        if artifact_priority_path is not None:
            artifact_priority_payload = load_json(artifact_priority_path) or {}
            artifact_priority_items = artifact_priority_payload.get("items", [])
            with st.expander("AI artifact priority", expanded=False):
                st.caption(f"Loaded artifact priority: {artifact_priority_path}")
                if pd is not None and isinstance(artifact_priority_items, list) and artifact_priority_items:
                    st.dataframe(pd.DataFrame(artifact_priority_items), use_container_width=True, height=200)
                else:
                    st.code(json.dumps(artifact_priority_payload, indent=2, ensure_ascii=True)[:3000], language="json")

        if compare_candidates:
            with st.expander("Case diff lane", expanded=False):
                st.caption("Use compare after you understand the current case root and need to explain differences across runs or exports.")
                compare_choice = st.selectbox(
                    "Compare against another case root",
                    ["(none)"] + [str(path) for path in compare_candidates],
                    index=0,
                )
                if compare_choice != "(none)":
                    diff_summary = build_case_diff_summary(
                        build_case_diff_payload(review_root, Path(compare_choice).expanduser().resolve())
                    )
                    st.markdown("**Case diff summary**")
                    st.code(diff_summary, language="markdown")

    with timeline_tab:
        render_dashboard_section_header(
            "Timeline",
            "Follow event flow only after the overview already makes sense.",
            "This is the incident-timeline lane: filter chronology, inspect source files, and compare source distribution without letting raw event volume bury your first read.",
        )
        timeline_json_path = find_latest_file(review_root, "timeline_events_*.json", recursive_scan)
        if timeline_json_path:
            timeline_payload = load_json(timeline_json_path) or {}
            events = timeline_payload.get("events", [])
            st.caption(f"Loaded timeline: {timeline_json_path}")
        else:
            events = []
            st.info("No timeline_events_*.json file was found. Run the timeline command first.")

        if events:
            if pd is None:
                st.warning("pandas is not installed, so the timeline table cannot be shown.")
            else:
                df = pd.DataFrame(events)
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

                left, mid, right = st.columns(3)
                with left:
                    sources = st.multiselect("Filter sources", sorted(df["source"].dropna().unique()), default=None)
                with mid:
                    types = st.multiselect("Filter event types", sorted(df["event_type"].dropna().unique()), default=None)
                with right:
                    keyword = st.text_input("Keyword filter (note_id/title/preview)", "")

                filtered = df
                if sources:
                    filtered = filtered[filtered["source"].isin(sources)]
                if types:
                    filtered = filtered[filtered["event_type"].isin(types)]
                if keyword:
                    keyword_lower = keyword.lower()
                    filtered = filtered[
                        filtered[["note_id", "note_title", "content_preview"]]
                        .fillna("")
                        .apply(lambda row: keyword_lower in " ".join(row).lower(), axis=1)
                    ]

                if px is not None and not filtered.empty:
                    fig = px.scatter(
                        filtered,
                        x="timestamp",
                        y="note_id",
                        color="event_type",
                        hover_data=["source", "note_title", "content_preview", "source_detail"],
                    )
                    fig.update_layout(height=420)
                    selection = st.plotly_chart(
                        fig,
                        use_container_width=True,
                        on_select="rerun",
                        selection_mode="points",
                    )
                    if selection and selection.get("selection", {}).get("points"):
                        idx = selection["selection"]["points"][0]["pointIndex"]
                        if 0 <= idx < len(filtered):
                            row = filtered.iloc[idx]
                            st.info("Timeline event selected. Preparing a source-file link.")
                            source_detail = str(row.get("source_detail", ""))
                            source_path = extract_source_path(source_detail)
                            if source_path:
                                file_uri = source_path.as_uri()
                                st.markdown(f"[Open source file]({file_uri})")
                                st.code(str(source_path))
                            else:
                                st.warning("source_detail could not be resolved to a valid path.")
                    else:
                        st.caption("Tip: if chart selection is unavailable, use the manual event selector below.")
                else:
                    st.info("Plotly is unavailable or there is no data, so the timeline chart was skipped.")

                st.dataframe(filtered, use_container_width=True, height=320)
                st.markdown("**Manual event selection**")
                if not filtered.empty:
                    filtered_indexed = filtered.reset_index(drop=True)
                    choices = [
                        f"{idx} | {row.get('timestamp', '')} | {row.get('event_type', '')} | {row.get('note_id', '')}"
                        for idx, row in filtered_indexed.iterrows()
                    ]
                    selected = st.selectbox("Select a timeline event", choices, index=0)
                    selected_idx = int(selected.split(" | ", 1)[0])
                    row = filtered_indexed.iloc[selected_idx]
                    source_detail = str(row.get("source_detail", ""))
                    source_path = extract_source_path(source_detail)
                    if source_path:
                        st.markdown(f"[Open source file]({source_path.as_uri()})")
                        st.code(str(source_path))
                    else:
                        st.warning("source_detail could not be resolved to a valid path.")
                else:
                    st.info("No timeline events are available for selection.")

        st.markdown("**Recovery source comparison**")
        timeline_summary_path = find_latest_file(review_root, "timeline_summary_*.json", recursive_scan)
        if timeline_summary_path:
            summary = load_json(timeline_summary_path) or {}
            by_source = summary.get("by_source", {})
            if pd is not None and by_source:
                df_source = pd.DataFrame(list(by_source.items()), columns=["source", "count"])
                if px is not None:
                    fig = px.bar(df_source, x="source", y="count", title="Timeline source distribution")
                    st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_source, use_container_width=True)
        else:
            st.info("timeline_summary_*.json was not found.")

    with spotlight_tab:
        render_dashboard_section_header(
            "Spotlight",
            "Use metadata and token views when you need pattern recognition, not when you need the first story.",
            "This tab groups the wider search surfaces together: metadata totals, event filters, and keyword density. It is the right lane for clustering and drift spotting.",
        )
        st.markdown("**Spotlight metadata**")
        spotlight_meta_path = find_latest_file(review_root, "spotlight_metadata_*.json", recursive_scan)
        if spotlight_meta_path:
            meta = load_json(spotlight_meta_path) or {}
            st.caption(f"Loaded Spotlight metadata: {spotlight_meta_path}")
            cols = st.columns(4)
            cols[0].metric("Files Scanned", meta.get("files_scanned", 0))
            cols[1].metric("Search Terms", len(meta.get("search_terms_top", [])))
            cols[2].metric("Bundle IDs", len(meta.get("bundle_ids_top", [])))
            cols[3].metric("File Paths", len(meta.get("file_paths_top", [])))

            def render_top(title: str, items: list[Any]):
                st.markdown(f"**{title}**")
                if not items:
                    st.write("(none)")
                    return
                if pd is None:
                    st.write(items[:15])
                    return
                df_items = pd.DataFrame(items, columns=["value", "count"])
                st.dataframe(df_items.head(15), use_container_width=True)

            left, right = st.columns(2)
            with left:
                render_top("Search term candidates", meta.get("search_terms_top", []))
                render_top("Note access frequency", meta.get("note_access_top", []))
            with right:
                render_top("Related app bundle IDs", meta.get("bundle_ids_top", []))
                render_top("Related file paths", meta.get("file_paths_top", []))
        else:
            st.info("Spotlight metadata was not found. Run spotlight-parse or timeline first.")

        st.markdown("**Spotlight event filters**")
        spotlight_events_path = find_latest_file(review_root, "spotlight_events_*.csv", recursive_scan)
        if spotlight_events_path:
            st.caption(f"Loaded Spotlight events: {spotlight_events_path}")
            if pd is None:
                st.warning("pandas is not installed, so the Spotlight events table cannot be shown.")
            else:
                spot_df = load_csv(spotlight_events_path)
                if spot_df is None or spot_df.empty:
                    st.info("Spotlight events are empty.")
                else:
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        table_filter = st.multiselect("Filter tables", sorted(spot_df["table"].dropna().unique()), default=None)
                    with c2:
                        column_filter = st.multiselect("Filter columns", sorted(spot_df["column"].dropna().unique()), default=None)
                    with c3:
                        note_filter = st.multiselect("Filter Note IDs", sorted(spot_df["note_id"].dropna().unique()), default=None)
                    keyword_filter = st.text_input("Event keyword filter (raw_value/source_path)", "")

                    filtered_events = spot_df
                    if table_filter:
                        filtered_events = filtered_events[filtered_events["table"].isin(table_filter)]
                    if column_filter:
                        filtered_events = filtered_events[filtered_events["column"].isin(column_filter)]
                    if note_filter:
                        filtered_events = filtered_events[filtered_events["note_id"].isin(note_filter)]
                    if keyword_filter:
                        kw_lower = keyword_filter.lower()
                        filtered_events = filtered_events[
                            filtered_events[["raw_value", "source_path"]]
                            .fillna("")
                            .apply(lambda row: kw_lower in " ".join(row).lower(), axis=1)
                        ]

                    st.dataframe(filtered_events, use_container_width=True, height=280)
                    if "timestamp_utc" in filtered_events.columns:
                        ts_df = filtered_events.copy()
                        ts_df["timestamp_utc"] = pd.to_datetime(ts_df["timestamp_utc"], errors="coerce")
                        ts_df = ts_df.dropna(subset=["timestamp_utc"])
                        if not ts_df.empty:
                            st.markdown("**Event time distribution (histogram)**")
                            bin_unit = st.selectbox("Time grain", ["hour", "day", "week"], index=1, key="spotlight_hist_bin")
                            freq_map = {"hour": "H", "day": "D", "week": "W"}
                            timestamp_series = ts_df["timestamp_utc"]
                            if getattr(timestamp_series.dt, "tz", None) is not None:
                                timestamp_series = timestamp_series.dt.tz_localize(None)
                            bucket = timestamp_series.dt.to_period(freq_map[bin_unit]).dt.start_time
                            hist_df = bucket.value_counts().reset_index()
                            hist_df.columns = ["bucket", "count"]
                            hist_df = hist_df.sort_values("bucket")
                            if px is not None:
                                fig = px.bar(hist_df, x="bucket", y="count", labels={"bucket": "time", "count": "events"})
                                fig.update_layout(height=320)
                                st.plotly_chart(fig, use_container_width=True)
                            st.dataframe(hist_df, use_container_width=True, height=240)
                    st.markdown("**Source file links for events**")
                    if not filtered_events.empty:
                        filtered_events = filtered_events.reset_index(drop=True)
                        choices = [
                            f"{idx} | {row.get('timestamp_utc', '')} | {row.get('table', '')}.{row.get('column', '')}"
                            for idx, row in filtered_events.iterrows()
                        ]
                        selected = st.selectbox("Select a Spotlight event", choices, index=0)
                        selected_idx = int(selected.split(" | ", 1)[0])
                        row = filtered_events.iloc[selected_idx]
                        source_path = Path(str(row.get("source_path", ""))).expanduser()
                        if source_path.exists():
                            st.markdown(f"[Open source file]({source_path.as_uri()})")
                            st.code(str(source_path))
                        else:
                            st.warning("source_path could not be located.")
        else:
            st.info("spotlight_events_*.csv was not found.")

        st.markdown("**Keyword heatmap**")
        spotlight_tokens_path = find_latest_file(review_root, "spotlight_tokens_*.csv", recursive_scan)
        if spotlight_tokens_path and pd is not None:
            tokens_df = load_csv(spotlight_tokens_path)
            if tokens_df is None or tokens_df.empty:
                st.info("Spotlight keyword data is empty.")
            else:
                st.caption(f"Loaded Spotlight keywords: {spotlight_tokens_path}")
                categories = sorted(tokens_df["category"].dropna().unique())
                category = st.selectbox("Keyword category", categories, index=categories.index("query") if "query" in categories else 0)
                top_n = st.slider("Top N", min_value=5, max_value=50, value=20, step=5)
                filtered_tokens = tokens_df[tokens_df["category"] == category].sort_values("count", ascending=False).head(top_n)
                if plotly_graph_objects is not None and not filtered_tokens.empty:
                    z = filtered_tokens[["count"]].values
                    fig = plotly_graph_objects.Figure(
                        data=plotly_graph_objects.Heatmap(
                            z=z,
                            x=["count"],
                            y=filtered_tokens["value"].tolist(),
                            colorscale="YlOrRd",
                            showscale=True,
                        )
                    )
                    fig.update_layout(height=420, margin=dict(l=20, r=20, t=20, b=20))
                    st.plotly_chart(fig, use_container_width=True)
                st.dataframe(filtered_tokens, use_container_width=True, height=260)
        else:
            st.info("spotlight_tokens_*.csv was not found, or pandas is unavailable.")

    with stitched_tab:
        render_dashboard_section_header(
            "Stitched review",
            "This is the candidate-review lane for merged fragments and operator verdicts.",
            "Use it after timeline or Spotlight work has already narrowed your attention. The graph helps explain relationships; the verdict form captures what survived review.",
        )
        fragments_manifest = find_latest_file(review_root, "fragments_manifest_*.csv", recursive_scan)
        stitched_manifest = find_latest_file(review_root, "stitched_manifest_*.csv", recursive_scan)

        st.markdown("**Fragment relationship graph**")
        if fragments_manifest and stitched_manifest and networkx is not None and plotly_graph_objects is not None:
            frag_df = load_csv(fragments_manifest)
            stitch_df = load_csv(stitched_manifest)
            if frag_df is not None and stitch_df is not None:
                G = networkx.Graph()
                for _idx, row in frag_df.iterrows():
                    node_id = f"F{int(row['id'])}"
                    G.add_node(node_id, label=node_id, group="fragment")
                for _idx, row in stitch_df.iterrows():
                    node_id = f"S{int(row['id'])}"
                    G.add_node(node_id, label=node_id, group="stitched")
                    frag_ids = str(row.get("fragment_ids", "")).split(",")
                    for frag in frag_ids:
                        frag = frag.strip()
                        if not frag:
                            continue
                        G.add_edge(node_id, f"F{frag}")
                pos = networkx.spring_layout(G, seed=42, k=0.6)
                edge_x = []
                edge_y = []
                for a, b in G.edges():
                    x0, y0 = pos[a]
                    x1, y1 = pos[b]
                    edge_x += [x0, x1, None]
                    edge_y += [y0, y1, None]
                edge_trace = plotly_graph_objects.Scatter(
                    x=edge_x,
                    y=edge_y,
                    line=dict(width=0.6, color="#94a3b8"),
                    hoverinfo="none",
                    mode="lines",
                )
                node_x = []
                node_y = []
                node_text = []
                node_color = []
                for node, attrs in G.nodes(data=True):
                    x, y = pos[node]
                    node_x.append(x)
                    node_y.append(y)
                    node_text.append(node)
                    node_color.append("#6366f1" if attrs.get("group") == "stitched" else "#22c55e")
                node_trace = plotly_graph_objects.Scatter(
                    x=node_x,
                    y=node_y,
                    mode="markers+text",
                    text=node_text,
                    textposition="top center",
                    hoverinfo="text",
                    marker=dict(size=10, color=node_color),
                )
                fig = plotly_graph_objects.Figure(data=[edge_trace, node_trace])
                fig.update_layout(height=420, showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Failed to load fragments or stitched manifests.")
        else:
            st.info("Fragment data was not found, or networkx/plotly dependencies are unavailable.")

        st.markdown("**Stitched review**")
        if stitched_manifest:
            st.caption(f"Loaded stitched manifest: {stitched_manifest}")
            if pd is None:
                st.warning("pandas is not installed, so stitched review cannot be shown.")
            else:
                stitch_df = load_csv(stitched_manifest)
                if stitch_df is None or stitch_df.empty:
                    st.info("The stitched manifest is empty.")
                else:
                    review_path = review_root / "Review" / "stitched_review.csv"
                    review_df = load_review_csv(review_path)
                    fragments_lookup = build_fragment_lookup(fragments_manifest) if fragments_manifest else {}

                    stitch_df = stitch_df.fillna("")
                    stitch_df["id"] = stitch_df["id"].astype(int, errors="ignore")
                    stitch_df["length"] = stitch_df["length"].astype(int, errors="ignore")
                    stitch_df["score"] = stitch_df["score"].astype(str)
                    stitch_df["confidence"] = stitch_df.get("confidence", "").astype(str)
                    stitch_df["cluster_id"] = stitch_df.get("cluster_id", "").astype(str)

                    st.markdown("**Candidate list**")
                    st.dataframe(
                        stitch_df[["id", "sources", "cluster_id", "occurrences", "length", "score", "confidence"]]
                        if "cluster_id" in stitch_df.columns and "confidence" in stitch_df.columns
                        else stitch_df,
                        use_container_width=True,
                        height=260,
                    )

                    st.markdown("**Select a candidate for review**")
                    choices = [
                        f"{row['id']} | len={row.get('length','')} | score={row.get('score','')} | conf={row.get('confidence','')}"
                        for _idx, row in stitch_df.iterrows()
                    ]
                    selected = st.selectbox("Select a stitched record", choices, index=0)
                    selected_id = int(str(selected).split(" | ", 1)[0])
                    selected_row = stitch_df[stitch_df["id"] == selected_id].iloc[0]

                    md_path = Path(str(selected_row.get("md_path", "")))
                    txt_path = Path(str(selected_row.get("txt_path", "")))
                    html_path = Path(str(selected_row.get("html_path", "")))

                    st.markdown("**Stitched file links**")
                    for label, path in (("Markdown", md_path), ("Text", txt_path), ("HTML", html_path)):
                        if path.exists():
                            st.markdown(f"- [{label}]({path.as_uri()})")
                        else:
                            st.markdown(f"- {label}: (missing)")

                    preview_text = ""
                    if txt_path.exists():
                        preview_text = safe_read_text(txt_path, 6000)
                    elif md_path.exists():
                        preview_text = safe_read_text(md_path, 6000)
                    if preview_text:
                        st.markdown("**Stitched content preview**")
                        st.code(preview_text, language="text")

                    if fragments_lookup:
                        st.markdown("**Fragment chain links**")
                        frag_ids = [int(x) for x in str(selected_row.get("fragment_ids", "")).split(",") if x.strip().isdigit()]
                        if frag_ids:
                            for frag_id in frag_ids[:50]:
                                meta = fragments_lookup.get(frag_id, {})
                                frag_md = Path(meta.get("md_path", ""))
                                frag_txt = Path(meta.get("txt_path", ""))
                                frag_html = Path(meta.get("html_path", ""))
                                label = meta.get("detail", "") or meta.get("source", "")
                                st.markdown(f"- Fragment {frag_id}: {label}")
                                links = []
                                if frag_md.exists():
                                    links.append(f"[md]({frag_md.as_uri()})")
                                if frag_txt.exists():
                                    links.append(f"[txt]({frag_txt.as_uri()})")
                                if frag_html.exists():
                                    links.append(f"[html]({frag_html.as_uri()})")
                                if links:
                                    st.markdown("  - " + " ".join(links))
                        else:
                            st.info("No fragment_ids were found.")

                    st.markdown("**Review verdict**")
                    existing_verdict = "Unreviewed"
                    existing_note = ""
                    if review_df is not None and not review_df.empty:
                        existing = review_df[review_df["stitched_id"] == selected_id]
                        if not existing.empty:
                            existing_verdict = existing.iloc[0].get("verdict", "Unreviewed")
                            existing_note = existing.iloc[0].get("note", "")

                    with st.form("review_form", clear_on_submit=False):
                        verdict = st.radio("Candidate verdict", ["Unreviewed", "True candidate", "False candidate"], index=["Unreviewed", "True candidate", "False candidate"].index(existing_verdict))
                        note = st.text_area("Notes", value=existing_note, height=80)
                        submitted = st.form_submit_button("Save review")
                        if submitted and review_df is not None:
                            review_df = upsert_review_row(
                                review_df,
                                {
                                    "stitched_id": selected_id,
                                    "verdict": verdict,
                                    "note": note,
                                    "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                                    "sources": str(selected_row.get("sources", "")),
                                    "cluster_id": str(selected_row.get("cluster_id", "")),
                                    "length": selected_row.get("length", ""),
                                    "score": selected_row.get("score", ""),
                                    "confidence": selected_row.get("confidence", ""),
                                    "md_path": str(md_path),
                                    "txt_path": str(txt_path),
                                    "html_path": str(html_path),
                                },
                            )
                            if save_review_csv(review_path, review_df):
                                st.success(f"Saved to {review_path}")
                            else:
                                st.error("Save failed. Check the path permissions.")

                    if review_df is not None and not review_df.empty:
                        st.markdown("**Saved reviews**")
                        st.dataframe(review_df, use_container_width=True, height=220)
        else:
            st.info("stitched_manifest_*.csv was not found.")

    with st.expander("Optional future uplift", expanded=False):
        st.caption("Semantic search can be layered on later without changing the current local-first review contract.")


# =============================================================================
# Entry Point
# =============================================================================


def main() -> None:
    try:
        from streamlit.web import cli as stcli  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "streamlit is required: pip install streamlit plotly networkx pandas"
        ) from exc
    import sys
    sys.argv = ["streamlit", "run", str(Path(__file__))]
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    run_dashboard()
