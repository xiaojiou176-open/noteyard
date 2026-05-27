from pathlib import Path

from notes_recovery.config import DEFAULT_PLUGINS_CONFIG
from notes_recovery.services.plugins import ensure_plugins_config, load_plugins_config, resolve_plugin_output_dir
from notes_recovery.services import plugins


def test_plugins_config_roundtrip(tmp_path: Path) -> None:
    config_path = tmp_path / "plugins.json"
    ensure_plugins_config(config_path)
    tools = load_plugins_config(config_path)
    assert tools
    assert len(tools) == len(DEFAULT_PLUGINS_CONFIG["tools"])


def test_validate_plugins_config_default_config_is_ok(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "plugins.json"
    ensure_plugins_config(config_path)

    monkeypatch.setattr(plugins.shutil, "which", lambda _cmd: None)

    payload = plugins.validate_plugins_config(
        config_path,
        root_dir=tmp_path / "case",
        db_path=tmp_path / "case" / "DB_Backup" / "NoteStore.sqlite",
    )

    assert payload["status"] == "ok"
    assert payload["summary"] == {
        "ok": len(DEFAULT_PLUGINS_CONFIG["tools"]),
        "warn": 0,
        "fail": 0,
    }
    assert all(item["status"] == "ok" for item in payload["tools"])


def test_resolve_plugin_output_dir(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    out_dir = resolve_plugin_output_dir(root, "Plugins_Output/tool", "tool")
    assert out_dir == root / "Plugins_Output/tool"
