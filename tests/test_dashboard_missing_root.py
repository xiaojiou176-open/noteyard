from __future__ import annotations

from pathlib import Path

from notes_recovery.apps import dashboard


class _FakeContext:
    def __init__(self, st):
        self._st = st

    def __enter__(self):
        return self._st

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self, root_dir: Path):
        self._root_dir = root_dir
        self.sidebar = _FakeContext(self)

    def set_page_config(self, **_kwargs):
        return None

    def title(self, _text):
        return None

    def header(self, _text):
        return None

    def text_input(self, _label, value=""):
        return str(self._root_dir)

    def checkbox(self, _label, value=False):
        return value

    def caption(self, _text):
        return None

    def markdown(self, _text, **_kwargs):
        return None

    def tabs(self, labels):
        return [_FakeContext(self) for _ in labels]

    def expander(self, _label, expanded=False):
        return _FakeContext(self)

    def error(self, _text):
        return None

    def stop(self):
        raise SystemExit("st.stop")


def test_run_dashboard_missing_root(monkeypatch, tmp_path: Path) -> None:
    missing_root = tmp_path / "missing"
    fake_st = _FakeStreamlit(missing_root)

    def fake_import(name: str):
        if name == "streamlit":
            return fake_st
        return None

    monkeypatch.setattr(dashboard, "_try_import", fake_import)

    try:
        dashboard.run_dashboard()
    except SystemExit as exc:
        assert "st.stop" in str(exc)
