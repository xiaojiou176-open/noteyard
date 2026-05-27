import types
from pathlib import Path

import pytest

from notes_recovery.services import gui


class _FakeVar:
    def __init__(self, value=None):
        if isinstance(value, str) and value == "":
            value = "keyword"
        self._value = value
        self._traces = []

    def get(self):
        return self._value

    def set(self, value):
        self._value = value
        for cb in self._traces:
            cb("", "", "")

    def trace_add(self, _mode, callback):
        self._traces.append(callback)


class _FakeWidget:
    def __init__(self, *args, **kwargs):
        self._config = {}
        self.command = kwargs.get("command")
        self.text = kwargs.get("text", "")

    def grid(self, *args, **kwargs):
        return None

    def pack(self, *args, **kwargs):
        return None

    def columnconfigure(self, *args, **kwargs):
        return None

    def bind(self, *args, **kwargs):
        return None

    def bind_all(self, *args, **kwargs):
        return None

    def configure(self, **kwargs):
        self._config.update(kwargs)
        return None

    def config(self, **kwargs):
        return self.configure(**kwargs)

    def insert(self, *args, **kwargs):
        return None

    def delete(self, *args, **kwargs):
        return None

    def see(self, *args, **kwargs):
        return None

    def yview(self, *args, **kwargs):
        return None

    def set(self, *args, **kwargs):
        return None

    def yview_scroll(self, *args, **kwargs):
        return None

    def create_window(self, *args, **kwargs):
        return None

    def add(self, *args, **kwargs):
        return None


class _FakeText(_FakeWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text = ""

    def insert(self, _pos, text):
        self._text += text

    def get(self, _start, _end):
        return self._text


class _FakeProgressbar(_FakeWidget):
    def start(self, *args, **kwargs):
        return None

    def stop(self):
        return None


class _FakeCanvas(_FakeWidget):
    def bbox(self, _arg):
        return (0, 0, 1, 1)


class _FakeStyle:
    def __init__(self, *args, **kwargs):
        return None

    def theme_names(self):
        return ["aqua"]

    def theme_use(self, _name):
        return None


class _FakeTk(_FakeWidget):
    def __init__(self):
        super().__init__()
        self._after_callbacks = []

    def title(self, _text):
        return None

    def geometry(self, _text):
        return None

    def minsize(self, *_args):
        return None

    def register(self, func):
        return func

    def after(self, _delay, func):
        self._after_callbacks.append(func)

    def mainloop(self):
        for func in list(self._after_callbacks):
            func()
        for cmd in list(_BUTTON_COMMANDS):
            cmd()

    def clipboard_clear(self):
        return None

    def clipboard_append(self, _text):
        return None


class _FakeTtk(types.SimpleNamespace):
    def __init__(self):
        super().__init__(
            Style=_FakeStyle,
            Panedwindow=_FakeWidget,
            Frame=_FakeWidget,
            Labelframe=_FakeWidget,
            Label=_FakeWidget,
            Entry=_FakeWidget,
            Button=_fake_button,
            Checkbutton=_FakeWidget,
            Separator=_FakeWidget,
            Scrollbar=_FakeWidget,
            Progressbar=_FakeProgressbar,
            Combobox=_FakeWidget,
        )


class _FakeFileDialog:
    def askdirectory(self):
        return ""


class _FakeMessageBox:
    def __init__(self):
        self.errors = []

    def showerror(self, title, message):
        self.errors.append((title, message))


_BUTTON_COMMANDS = []


def _fake_button(*args, **kwargs):
    widget = _FakeWidget(*args, **kwargs)
    if widget.command:
        _BUTTON_COMMANDS.append(widget.command)
    return widget


class _ImmediateThread:
    def __init__(self, target=None, daemon=None):
        self._target = target

    def start(self):
        if self._target:
            self._target()


@pytest.fixture(autouse=True)
def _patch_tk(monkeypatch, tmp_path: Path):
    _BUTTON_COMMANDS.clear()
    fake_tk = types.SimpleNamespace(
        Tk=_FakeTk,
        StringVar=_FakeVar,
        BooleanVar=_FakeVar,
        IntVar=_FakeVar,
        DoubleVar=_FakeVar,
        Text=_FakeText,
        Canvas=_FakeCanvas,
        Event=object,
        Widget=_FakeWidget,
        TclError=Exception,
    )
    fake_tk.ttk = _FakeTtk()
    fake_tk.filedialog = _FakeFileDialog()
    fake_tk.messagebox = _FakeMessageBox()
    fake_tk.END = "end"

    monkeypatch.setitem(__import__("sys").modules, "tkinter", fake_tk)
    monkeypatch.setitem(__import__("sys").modules, "tkinter.ttk", fake_tk.ttk)
    monkeypatch.setitem(__import__("sys").modules, "tkinter.filedialog", fake_tk.filedialog)
    monkeypatch.setitem(__import__("sys").modules, "tkinter.messagebox", fake_tk.messagebox)

    monkeypatch.setattr(gui, "threading", types.SimpleNamespace(Thread=_ImmediateThread))
    monkeypatch.setattr(gui, "resolve_log_path", lambda *_args, **_kwargs: None)

    calls = []

    def fake_auto_run(*args, **kwargs):
        calls.append((args, kwargs))
        print(f"Timestamped output directory: {tmp_path / 'Notes_Forensics'}")

    monkeypatch.setattr(gui, "auto_run", fake_auto_run)

    return calls


def test_run_gui_smoke(_patch_tk):
    gui.run_gui()
    assert _patch_tk, "auto_run should be called"


def test_validate_helpers():
    assert gui.validate_int_text("123")
    assert not gui.validate_int_text("12a")
    assert gui.validate_float_text("1.23")
    assert not gui.validate_float_text("abc")


def test_open_in_file_manager_missing(tmp_path: Path):
    missing = tmp_path / "nope"
    with pytest.raises(RuntimeError):
        gui.open_in_file_manager(missing)
