import json
from pathlib import Path

import notes_recovery.services.plugins as plugins


def test_run_plugins_with_manifest(monkeypatch, tmp_path: Path) -> None:
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    db_path = root_dir / "NoteStore.sqlite"
    db_path.write_text("db", encoding="utf-8")

    config_path = root_dir / "plugins.json"
    config = {
        "tools": [
            {
                "name": "disabled_tool",
                "enabled": False,
                "output_dir": "Plugins_Output/disabled",
                "command": ["echo", "skip"],
            },
            {
                "name": "placeholder_tool",
                "enabled": True,
                "output_dir": "Plugins_Output/placeholder",
                "command": ["path/to/tool"],
            },
            {
                "name": "echo_tool",
                "enabled": True,
                "output_dir": "Plugins_Output/echo",
                "command": ["echo", "hello"],
            },
        ]
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    calls = []

    def fake_run(cmd, check, stdout, stderr, text, timeout=None):
        calls.append(cmd)
        return None

    monkeypatch.setattr(plugins.subprocess, "run", fake_run)

    plugins.run_plugins(
        root_dir=root_dir,
        db_path=db_path,
        config_path=config_path,
        enable_all=False,
        run_ts="20260101_000000",
    )

    manifest = root_dir / "plugins_manifest_20260101_000000.jsonl"
    assert manifest.exists()
    lines = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    statuses = {item["tool"]: item["status"] for item in lines}
    assert statuses.get("disabled_tool") == "skipped"
    assert statuses.get("placeholder_tool") == "skipped"
    assert statuses.get("echo_tool") == "ok"
    assert calls


def test_run_plugins_skips_host_control_commands(monkeypatch, tmp_path: Path) -> None:
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    db_path = root_dir / "NoteStore.sqlite"
    db_path.write_text("db", encoding="utf-8")

    config_path = root_dir / "plugins.json"
    config = {
        "tools": [
            {
                "name": "dangerous_tool",
                "enabled": True,
                "output_dir": "Plugins_Output/dangerous",
                "command": ["killall", "Finder"],
            }
        ]
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    calls = []

    def fake_run(cmd, check, stdout, stderr, text, timeout=None):
        calls.append(cmd)
        return None

    monkeypatch.setattr(plugins.subprocess, "run", fake_run)

    plugins.run_plugins(
        root_dir=root_dir,
        db_path=db_path,
        config_path=config_path,
        enable_all=False,
        run_ts="20260101_000001",
    )

    manifest = root_dir / "plugins_manifest_20260101_000001.jsonl"
    assert manifest.exists()
    lines = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["status"] == "skipped"
    assert "host-control executable" in lines[0]["reason"]
    assert calls == []


def test_run_plugins_skips_env_wrapped_host_control_commands(monkeypatch, tmp_path: Path) -> None:
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    db_path = root_dir / "NoteStore.sqlite"
    db_path.write_text("db", encoding="utf-8")

    config_path = root_dir / "plugins.json"
    config = {
        "tools": [
            {
                "name": "wrapped_dangerous_tool",
                "enabled": True,
                "output_dir": "Plugins_Output/wrapped-dangerous",
                "command": ["env", "killall", "Finder"],
            }
        ]
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    calls = []

    def fake_run(cmd, check, stdout, stderr, text, timeout=None):
        calls.append(cmd)
        return None

    monkeypatch.setattr(plugins.subprocess, "run", fake_run)

    plugins.run_plugins(
        root_dir=root_dir,
        db_path=db_path,
        config_path=config_path,
        enable_all=False,
        run_ts="20260101_000002",
    )

    manifest = root_dir / "plugins_manifest_20260101_000002.jsonl"
    assert manifest.exists()
    lines = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["status"] == "skipped"
    assert "host-control executable" in lines[0]["reason"]
    assert calls == []
