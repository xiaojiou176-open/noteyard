from __future__ import annotations

import json
from pathlib import Path

import pytest

from notes_recovery.services import plugins


def test_load_plugins_config_and_run(tmp_path: Path) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    root_dir.mkdir()
    db_path = root_dir / "DB_Backup" / "NoteStore.sqlite"
    db_path.parent.mkdir(parents=True)
    db_path.write_text("db", encoding="utf-8")

    config_path = tmp_path / "plugins.json"
    config = {
        "tools": [
            {
                "name": "disabled",
                "command": ["echo", "skip"],
                "enabled": False,
                "output_dir": "Plugins_Output/disabled",
            },
            {
                "name": "placeholder",
                "command": ["path/to/tool", "{db}"],
                "enabled": True,
                "output_dir": "Plugins_Output/placeholder",
            },
            {
                "name": "bad_out",
                "command": ["echo", "bad"],
                "enabled": True,
                "output_dir": "/abs/path",
            },
            {
                "name": "ok",
                "command": "/bin/echo ok {db}",
                "enabled": True,
                "output_dir": "Plugins_Output/ok",
                "timeout_sec": "2",
            },
        ]
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    tools = plugins.load_plugins_config(config_path)
    assert len(tools) == 4
    assert tools[-1].timeout_sec == 2

    plugins.run_plugins(root_dir, db_path, config_path, enable_all=False, run_ts="20260101_000000")
    manifest = root_dir / "plugins_manifest_20260101_000000.jsonl"
    assert manifest.exists()
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert lines


def test_resolve_plugin_output_dir_errors(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        plugins.resolve_plugin_output_dir(tmp_path, "/abs", "tool")
    with pytest.raises(RuntimeError):
        plugins.resolve_plugin_output_dir(tmp_path, "../bad", "tool")


def test_ensure_plugins_config_creates_default(tmp_path: Path) -> None:
    config_path = tmp_path / "default_plugins.json"
    plugins.ensure_plugins_config(config_path)
    assert config_path.exists()


def test_run_plugins_failure_and_timeout(tmp_path: Path, monkeypatch) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    root_dir.mkdir()
    db_path = root_dir / "DB_Backup" / "NoteStore.sqlite"
    db_path.parent.mkdir(parents=True)
    db_path.write_text("db", encoding="utf-8")

    config_path = tmp_path / "plugins.json"
    config = {
        "tools": [
            {"name": "fail", "command": ["/bin/echo", "x"], "enabled": True, "output_dir": "Plugins_Output/fail"},
            {"name": "timeout", "command": ["/bin/echo", "y"], "enabled": True, "output_dir": "Plugins_Output/timeout"},
        ]
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    calls = {"count": 0}

    def fake_run(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise plugins.subprocess.CalledProcessError(1, ["cmd"], "err")
        raise plugins.subprocess.TimeoutExpired(cmd=["cmd"], timeout=1)

    monkeypatch.setattr(plugins.subprocess, "run", fake_run)

    plugins.run_plugins(root_dir, db_path, config_path, enable_all=False, run_ts="20260102_000000")
    manifest = root_dir / "plugins_manifest_20260102_000000.jsonl"
    text = manifest.read_text(encoding="utf-8")
    assert "failed" in text
    assert "timeout" in text


def test_run_plugins_formats_db_path_placeholder(tmp_path: Path, monkeypatch) -> None:
    root_dir = tmp_path / "Notes_Forensics"
    root_dir.mkdir()
    db_path = root_dir / "DB_Backup" / "NoteStore.sqlite"
    db_path.parent.mkdir(parents=True)
    db_path.write_text("db", encoding="utf-8")

    config_path = tmp_path / "plugins.json"
    config = {
        "tools": [
            {
                "name": "format_db_path",
                "command": ["/bin/echo", "{db_path}", "{out}"],
                "enabled": True,
                "output_dir": "Plugins_Output/formatted",
            }
        ]
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return None

    monkeypatch.setattr(plugins.subprocess, "run", fake_run)

    plugins.run_plugins(root_dir, db_path, config_path, enable_all=False, run_ts="20260103_000000")

    assert calls
    assert calls[0][1] == str(db_path)
    assert calls[0][2].endswith("Plugins_Output/formatted_20260103_000000")
