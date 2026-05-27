from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from notes_recovery.services import snapshot


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_warn_if_notes_running_and_error(monkeypatch) -> None:
    calls = []

    def fake_eprint(msg: str) -> None:
        calls.append(msg)

    def fake_run(*_args, **_kwargs):
        return _FakeCompleted(0)

    monkeypatch.setattr(snapshot, "eprint", fake_eprint)
    monkeypatch.setattr(snapshot.subprocess, "run", fake_run)
    snapshot.warn_if_notes_running()
    assert calls

    def boom(*_args, **_kwargs):
        raise RuntimeError("pgrep fail")

    monkeypatch.setattr(snapshot.subprocess, "run", boom)
    snapshot.warn_if_notes_running()


def test_run_cmd_success_and_error(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):
        return _FakeCompleted(0, stdout="ok\n", stderr="warn\n")

    monkeypatch.setattr(snapshot.subprocess, "run", fake_run)
    snapshot.run_cmd(["echo", "ok"])

    def fake_error(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "cmd", stderr="boom")

    monkeypatch.setattr(snapshot.subprocess, "run", fake_error)
    with pytest.raises(RuntimeError):
        snapshot.run_cmd(["false"])


def test_copy_path_fallback_and_missing(tmp_path: Path, monkeypatch) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "file.txt").write_text("data", encoding="utf-8")
    dst_dir = tmp_path / "dst"

    def boom(*_args, **_kwargs):
        raise RuntimeError("ditto fail")

    monkeypatch.setattr(snapshot, "copy_with_ditto", boom)
    snapshot.copy_path(src_dir, dst_dir)
    assert (dst_dir / "file.txt").exists()

    with pytest.raises(RuntimeError):
        snapshot.copy_path(tmp_path / "missing", tmp_path / "out")
