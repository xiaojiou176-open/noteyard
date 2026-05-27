from __future__ import annotations

import datetime
import types
from pathlib import Path

import notes_recovery.services.timeline as timeline
from notes_recovery.models import TimelineEvent, TimelineEventType, TimelineSource


class _FakeFigure:
    def __init__(self, data=None):
        self.data = data

    def update_layout(self, **_kwargs) -> None:
        return None

    def write_html(self, path: str, include_plotlyjs: str = "cdn") -> None:
        Path(path).write_text("plot", encoding="utf-8")


class _FakeGO(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("plotly.graph_objects")

    def Scatter(self, **kwargs):  # noqa: N802
        return kwargs

    def Figure(self, data=None):  # noqa: N802
        return _FakeFigure(data=data)


def _make_event(ts: datetime.datetime, note_id: str, source: TimelineSource) -> TimelineEvent:
    return TimelineEvent(
        timestamp=ts,
        event_type=TimelineEventType.CREATED,
        source=source,
        note_id=note_id,
        note_title="title",
        content_preview="preview",
        source_detail="/tmp/source",
        confidence=0.5,
    )


def test_timeline_utils_and_outputs(tmp_path: Path, monkeypatch) -> None:
    ts = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    event = _make_event(ts, "note-1", TimelineSource.DB)
    events = [event]

    grouped = timeline.group_events_by_note(events)
    assert "note-1" in grouped

    csv_path = tmp_path / "timeline.csv"
    json_path = tmp_path / "timeline.json"
    summary_path = tmp_path / "summary.json"
    html_path = tmp_path / "timeline.html"

    timeline.write_timeline_csv(csv_path, events)
    assert csv_path.exists()

    timeline.write_timeline_json(json_path, events, grouped, spotlight_meta=None)
    assert json_path.exists()

    timeline.write_timeline_summary(summary_path, events, grouped, spotlight_meta=None)
    assert summary_path.exists()

    timeline.write_timeline_html(html_path, events, grouped, keyword="note", plotly_path=None, spotlight_meta=None)
    assert "Notes Timeline" in html_path.read_text(encoding="utf-8")

    fake_go = _FakeGO()
    monkeypatch.setitem(__import__("sys").modules, "plotly", types.ModuleType("plotly"))
    monkeypatch.setitem(__import__("sys").modules, "plotly.graph_objects", fake_go)
    plot_path = timeline.write_timeline_plotly(tmp_path / "plot.html", events)
    assert plot_path and plot_path.exists()


def test_timeline_anomaly_and_keyword_where() -> None:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    old = datetime.datetime(1999, 1, 1, tzinfo=datetime.timezone.utc)
    future = now + datetime.timedelta(days=3650)

    events = [
        _make_event(old, "note-1", TimelineSource.DB),
        _make_event(future, "note-1", TimelineSource.DB),
        _make_event(now - datetime.timedelta(days=1), "note-1", TimelineSource.DB),
    ]
    timeline.annotate_timeline_anomalies(events)
    assert any(e.anomaly for e in events)

    clause, params = timeline.build_keyword_where("t", ["title", "body"], "hello")
    assert "LIKE" in clause
    assert params

    old_event = timeline.make_timeline_event(old, TimelineEventType.CREATED, TimelineSource.DB, "", "", "", "", 0.1)
    assert old_event is not None
    timeline.annotate_timeline_anomalies([old_event])
    assert old_event.anomaly

    assert timeline.build_select_expr("t", "missing", {"a"}) == "NULL AS missing"
    assert timeline.build_timeline_preview() == ""


def test_timeline_wal_and_spotlight_events(tmp_path: Path) -> None:
    root = tmp_path / "root"
    db_dir = root / "DB_Backup"
    db_dir.mkdir(parents=True)
    wal = db_dir / "NoteStore.sqlite-wal"
    shm = db_dir / "NoteStore.sqlite-shm"
    wal.write_bytes(b"wal")
    shm.write_bytes(b"shm")

    isolation = db_dir / "WAL_Isolation"
    isolation.mkdir()
    (isolation / "extra.sqlite-wal").write_bytes(b"wal")

    wal_files = timeline.collect_wal_files(root)
    assert wal_files
    wal_events = timeline.extract_wal_events(wal_files)
    assert wal_events

    spot_dir = root / "Spotlight_Backup"
    spot_dir.mkdir()
    (spot_dir / "store.db").write_bytes(b"db")
    (spot_dir / "journalattr").write_bytes(b"j")
    spotlight_events = timeline.extract_spotlight_events(spot_dir, max_files=10)
    assert spotlight_events

    assert timeline.find_latest_file(root, "nope.*") is None
    assert timeline.find_latest_spotlight_analysis_dir(root) is None

    analysis_a = root / "Spotlight_Analysis_A"
    analysis_b = root / "Spotlight_Analysis_B"
    analysis_a.mkdir()
    analysis_b.mkdir()
    latest = timeline.find_latest_spotlight_analysis_dir(root)
    assert latest in {analysis_a, analysis_b}

    assert timeline.mac_absolute_to_datetime(None) is None
    assert timeline.unix_to_datetime(None) is None
    assert timeline.mac_absolute_to_datetime("bad") is None
    assert timeline.unix_to_datetime("bad") is None

    long_text = "x" * (timeline.TIMELINE_PREVIEW_MAX_CHARS + 10)
    preview = timeline.build_timeline_preview(long_text)
    assert preview.endswith("...")


def test_extract_db_events_unknown_schema(monkeypatch, tmp_path: Path) -> None:
    import sqlite3
    db_path = tmp_path / "db.sqlite"
    db_path.write_text("x", encoding="utf-8")

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    event = _make_event(datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc), "note", TimelineSource.DB)

    monkeypatch.setattr(timeline, "open_sqlite_readonly", lambda _p: conn)
    monkeypatch.setattr(timeline, "detect_schema", lambda _c: timeline.SchemaType.UNKNOWN)
    monkeypatch.setattr(timeline, "extract_db_events_icloud", lambda *_args, **_kwargs: [event])

    events = timeline.extract_db_events(db_path, keyword=None, max_notes=10)
    assert events
