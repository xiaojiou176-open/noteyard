from __future__ import annotations

from pathlib import Path

import pytest

from notes_recovery.apps import dashboard


class _MiniContext:
    def __init__(self, st):
        self._st = st

    def __enter__(self):
        return self._st

    def __exit__(self, exc_type, exc, tb):
        return False

    def __getattr__(self, name):
        return getattr(self._st, name)


class _MiniStreamlit:
    def __init__(self, root_dir: Path, stop_on_info: bool = False):
        self._root_dir = root_dir
        self.stop_on_info = stop_on_info
        self.sidebar = _MiniContext(self)

    def set_page_config(self, **_kwargs):
        return None

    def title(self, _text):
        return None

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
        return False

    def columns(self, count):
        return [_MiniContext(self) for _ in range(count)]

    def multiselect(self, _label, _options, default=None):
        return [] if default is None else default

    def metric(self, _label, _value):
        return None

    def markdown(self, _text, **_kwargs):
        return None

    def tabs(self, labels):
        return [_MiniContext(self) for _ in labels]

    def expander(self, _label, expanded=False):
        return _MiniContext(self)

    def code(self, _text, language=None):
        return None

    def info(self, _text):
        if self.stop_on_info:
            raise SystemExit("stop after info")
        return None

    def warning(self, _text):
        raise SystemExit("stop after warning")

    def error(self, _text):
        raise SystemExit("stop after error")

    def stop(self):
        raise SystemExit("st.stop called")


def test_run_dashboard_requires_streamlit(monkeypatch) -> None:
    def fake_import(name: str):
        return None if name == "streamlit" else None

    monkeypatch.setattr(dashboard, "_try_import", fake_import)
    with pytest.raises(SystemExit):
        dashboard.run_dashboard()


def test_run_dashboard_missing_timeline(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    st = _MiniStreamlit(root, stop_on_info=True)

    def fake_import(name: str):
        if name == "streamlit":
            return st
        if name == "pandas":
            return None
        if name == "networkx":
            return None
        return None

    monkeypatch.setattr(dashboard, "_try_import", fake_import)
    with pytest.raises(SystemExit):
        dashboard.run_dashboard()
