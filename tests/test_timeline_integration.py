import sqlite3
import types
from pathlib import Path

from notes_recovery.services import timeline


class _FakeScatter:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class _FakeFigure:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def update_layout(self, **kwargs):
        return None

    def write_html(self, path: str, include_plotlyjs: str = "cdn"):
        Path(path).write_text("plotly", encoding="utf-8")


class _FakeGraphObjects(types.SimpleNamespace):
    def __init__(self):
        super().__init__(Figure=_FakeFigure, Scatter=_FakeScatter)


def _write_spotlight_sqlite(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE events (note_id TEXT, ts INTEGER, info TEXT)")
    conn.execute("INSERT INTO events VALUES (?, ?, ?)", ("note1", 1700000000, "Title"))
    conn.commit()
    conn.close()


def test_build_timeline_integration(monkeypatch, tmp_path: Path) -> None:
    root_dir = tmp_path / "root"
    db_dir = root_dir / "DB_Backup"
    spot_dir = root_dir / "Spotlight_Backup"
    db_dir.mkdir(parents=True)
    spot_dir.mkdir(parents=True)

    source_db = Path(__file__).parent / "data" / "icloud_min.sqlite"
    (db_dir / "NoteStore.sqlite").write_bytes(source_db.read_bytes())
    (db_dir / "NoteStore.sqlite-wal").write_bytes(b"wal")

    # Spotlight files
    import plistlib
    with (spot_dir / "test.plist").open("wb") as f:
        plistlib.dump({"query": "Title"}, f)
    _write_spotlight_sqlite(spot_dir / "store.db")

    fake_go = _FakeGraphObjects()
    monkeypatch.setitem(__import__("sys").modules, "plotly", types.ModuleType("plotly"))
    monkeypatch.setitem(__import__("sys").modules, "plotly.graph_objects", fake_go)

    out_dir = tmp_path / "Timeline"
    outputs = timeline.build_timeline(
        root_dir=root_dir,
        out_dir=out_dir,
        keyword="Title",
        max_notes=50,
        max_events=200,
        spotlight_max_files=5,
        include_fs=True,
        enable_plotly=True,
        run_ts="20260101_000000",
    )

    assert Path(outputs["timeline_json"]).exists()
    assert Path(outputs["timeline_csv"]).exists()
    assert outputs["timeline_plotly"]

    # Legacy DB path coverage
    legacy_db = tmp_path / "legacy.sqlite"
    source_legacy = Path(__file__).parent / "data" / "legacy_min.sqlite"
    legacy_db.write_bytes(source_legacy.read_bytes())
    events = timeline.extract_db_events(legacy_db, None, max_notes=10)
    assert isinstance(events, list)
