import json
import types
from pathlib import Path

import pandas as pd

from notes_recovery.apps import dashboard


class _FakeFigure:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def update_layout(self, **kwargs):
        return None


class _FakePlotlyExpress(types.SimpleNamespace):
    def scatter(self, *args, **kwargs):
        return _FakeFigure(*args, **kwargs)

    def bar(self, *args, **kwargs):
        return _FakeFigure(*args, **kwargs)


class _FakeHeatmap:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeScatter:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class _FakePlotlyGraphObjects(types.SimpleNamespace):
    def __init__(self):
        super().__init__(Figure=_FakeFigure, Heatmap=_FakeHeatmap, Scatter=_FakeScatter)


class _FakeGraph:
    def __init__(self):
        self._nodes: dict[str, dict] = {}
        self._edges: list[tuple[str, str]] = []

    def add_node(self, node_id, **attrs):
        self._nodes[node_id] = attrs

    def add_edge(self, a, b):
        self._edges.append((a, b))

    def edges(self):
        return list(self._edges)

    def nodes(self, data=False):
        if not data:
            return list(self._nodes.keys())
        return [(node, attrs) for node, attrs in self._nodes.items()]


class _FakeNetworkx(types.SimpleNamespace):
    def __init__(self):
        super().__init__(Graph=_FakeGraph)

    def spring_layout(self, graph, seed=None, k=None):
        positions = {}
        for idx, node in enumerate(graph.nodes()):
            positions[node] = (float(idx), float(idx))
        return positions


class _FakeContext:
    def __init__(self, st):
        self._st = st

    def __enter__(self):
        return self._st

    def __exit__(self, exc_type, exc, tb):
        return False

    def __getattr__(self, name):
        return getattr(self._st, name)


class _FakeStreamlit:
    def __init__(self, root_dir: Path):
        self._root_dir = root_dir
        self.calls = []
        self.sidebar = _FakeContext(self)

    def set_page_config(self, **_kwargs):
        self.calls.append("set_page_config")

    def title(self, _text):
        self.calls.append("title")

    def header(self, _text):
        return None

    def subheader(self, _text):
        return None

    def caption(self, _text):
        return None

    def text_input(self, label, value=""):
        if "Output root" in label:
            return str(self._root_dir)
        return value

    def checkbox(self, _label, value=False):
        return value

    def columns(self, count):
        return [_FakeContext(self) for _ in range(count)]

    def multiselect(self, _label, _options, default=None):
        return [] if default is None else default

    def selectbox(self, _label, options, index=0, key=None):
        return options[index]

    def slider(self, _label, min_value=None, max_value=None, value=None, step=None):
        return value

    def plotly_chart(self, _fig, **_kwargs):
        return {"selection": {"points": [{"pointIndex": 0}]}}

    def dataframe(self, *_args, **_kwargs):
        return None

    def markdown(self, _text, **_kwargs):
        return None

    def tabs(self, labels):
        return [_FakeContext(self) for _ in labels]

    def expander(self, _label, expanded=False):
        return _FakeContext(self)

    def code(self, _text, language=None):
        return None

    def info(self, _text):
        return None

    def warning(self, _text):
        return None

    def error(self, _text):
        return None

    def success(self, _text):
        return None

    def stop(self):
        raise SystemExit("st.stop called")

    def metric(self, _label, _value):
        return None

    def form(self, _key, clear_on_submit=False):
        return _FakeContext(self)

    def form_submit_button(self, _label):
        return True

    def radio(self, _label, options, index=0):
        return options[index]

    def text_area(self, _label, value="", height=None):
        return value


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(header) + "\n")
        for row in rows:
            f.write(",".join(str(item) for item in row) + "\n")


def test_run_dashboard_full(monkeypatch, tmp_path: Path) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    root_dir.mkdir()

    source_file = root_dir / "source.txt"
    source_file.write_text("sample", encoding="utf-8")

    timeline_events = {
        "events": [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "source": "db",
                "event_type": "note",
                "note_id": "N1",
                "note_title": "Title",
                "content_preview": "Preview",
                "source_detail": f"{source_file}::table.col",
            }
        ]
    }
    (root_dir / "timeline_events_20260101.json").write_text(
        json.dumps(timeline_events),
        encoding="utf-8",
    )
    (root_dir / "timeline_summary_20260101.json").write_text(
        json.dumps({"by_source": {"db": 1}}),
        encoding="utf-8",
    )

    spotlight_meta = {
        "files_scanned": 1,
        "search_terms_top": [["keyword", 3]],
        "note_access_top": [["note", 2]],
        "bundle_ids_top": [["bundle", 1]],
        "file_paths_top": [["/tmp/file", 1]],
    }
    (root_dir / "spotlight_metadata_20260101.json").write_text(
        json.dumps(spotlight_meta),
        encoding="utf-8",
    )
    _write_csv(
        root_dir / "spotlight_events_20260101.csv",
        ["timestamp_utc", "table", "column", "note_id", "source_path", "raw_value"],
        [["2024-01-01T00:00:00Z", "table", "col", "note", str(source_file), "raw"]],
    )
    _write_csv(
        root_dir / "spotlight_tokens_20260101.csv",
        ["category", "value", "count"],
        [["query", "token", 5]],
    )

    fragments_manifest = root_dir / "fragments_manifest_20260101.csv"
    stitched_manifest = root_dir / "stitched_manifest_20260101.csv"
    md_path = root_dir / "frag.md"
    txt_path = root_dir / "frag.txt"
    html_path = root_dir / "frag.html"
    md_path.write_text("md", encoding="utf-8")
    txt_path.write_text("txt", encoding="utf-8")
    html_path.write_text("html", encoding="utf-8")
    _write_csv(
        fragments_manifest,
        ["id", "md_path", "txt_path", "html_path", "detail", "source"],
        [[1, str(md_path), str(txt_path), str(html_path), "detail", "source"]],
    )
    stitched_md = root_dir / "stitched.md"
    stitched_txt = root_dir / "stitched.txt"
    stitched_html = root_dir / "stitched.html"
    stitched_md.write_text("stitched", encoding="utf-8")
    stitched_txt.write_text("stitched text", encoding="utf-8")
    stitched_html.write_text("<p>stitched</p>", encoding="utf-8")
    _write_csv(
        stitched_manifest,
        [
            "id",
            "sources",
            "cluster_id",
            "occurrences",
            "length",
            "score",
            "confidence",
            "md_path",
            "txt_path",
            "html_path",
            "fragment_ids",
        ],
        [[1, "src", "c1", 2, 120, 9.5, 0.9, str(stitched_md), str(stitched_txt), str(stitched_html), "1"]],
    )

    fake_st = _FakeStreamlit(root_dir)
    fake_px = _FakePlotlyExpress()
    fake_go = _FakePlotlyGraphObjects()
    fake_nx = _FakeNetworkx()

    def fake_try_import(name: str):
        if name == "streamlit":
            return fake_st
        if name == "pandas":
            return pd
        if name == "networkx":
            return fake_nx
        return None

    monkeypatch.setattr(dashboard, "_try_import", fake_try_import)
    monkeypatch.setitem(__import__("sys").modules, "plotly", types.ModuleType("plotly"))
    monkeypatch.setitem(__import__("sys").modules, "plotly.express", fake_px)
    monkeypatch.setitem(__import__("sys").modules, "plotly.graph_objects", fake_go)

    dashboard.run_dashboard()

    review_path = root_dir / "Review" / "stitched_review.csv"
    assert review_path.exists()
    review_df = pd.read_csv(review_path)
    assert not review_df.empty

    latest = dashboard.find_latest_file(root_dir, "timeline_events_*.json", recursive=True)
    assert latest is not None
