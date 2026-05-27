from __future__ import annotations

import json
from pathlib import Path

from notes_recovery.services import plugins


def _write_plugins_config(tmp_path: Path, tools: list[dict[str, object]]) -> Path:
    config_path = tmp_path / "plugins.json"
    config_path.write_text(json.dumps({"tools": tools}), encoding="utf-8")
    return config_path


def test_validate_plugins_config_disabled_tool_is_ok(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_plugins_config(
        tmp_path,
        [
            {
                "name": "disabled_tool",
                "command": ["missing_tool", "{db_path}"],
                "enabled": False,
                "output_dir": "Plugins_Output/disabled",
                "timeout_sec": 60,
            }
        ],
    )

    monkeypatch.setattr(plugins.shutil, "which", lambda _cmd: None)

    payload = plugins.validate_plugins_config(
        config_path,
        root_dir=tmp_path / "case",
        db_path=tmp_path / "case" / "DB_Backup" / "NoteStore.sqlite",
    )

    assert payload["status"] == "ok"
    assert payload["summary"] == {"ok": 1, "warn": 0, "fail": 0}
    tool_payload = payload["tools"][0]
    assert tool_payload["status"] == "ok"
    assert tool_payload["reasons"] == []
    assert any("disabled by config" in check["detail"] for check in tool_payload["checks"])


def test_validate_plugins_config_warns_for_placeholder_command(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_plugins_config(
        tmp_path,
        [
            {
                "name": "placeholder_tool",
                "command": ["path/to/tool", "{db_path}"],
                "enabled": True,
                "output_dir": "Plugins_Output/placeholder",
            }
        ],
    )

    monkeypatch.setattr(plugins.shutil, "which", lambda _cmd: None)

    payload = plugins.validate_plugins_config(config_path)

    assert payload["status"] == "warn"
    assert payload["summary"] == {"ok": 0, "warn": 1, "fail": 0}
    assert payload["tools"][0]["placeholder"] is True
    assert any("placeholder" in reason.lower() for reason in payload["tools"][0]["reasons"])


def test_validate_plugins_config_fails_for_required_fields_and_timeout(tmp_path: Path) -> None:
    config_path = _write_plugins_config(
        tmp_path,
        [
            {
                "name": "",
                "command": [],
                "enabled": True,
                "output_dir": "Plugins_Output/bad",
                "timeout_sec": 0,
            }
        ],
    )

    payload = plugins.validate_plugins_config(config_path)

    assert payload["status"] == "fail"
    assert payload["summary"] == {"ok": 0, "warn": 0, "fail": 1}
    reasons = payload["tools"][0]["reasons"]
    assert "Tool is missing a non-empty `name`." in reasons
    assert "Tool command is empty." in reasons
    assert "timeout_sec must be a positive integer when provided." in reasons


def test_validate_plugins_config_fails_for_non_relative_output_dir(tmp_path: Path) -> None:
    config_path = _write_plugins_config(
        tmp_path,
        [
            {
                "name": "escape_tool",
                "command": ["/bin/echo", "ok"],
                "enabled": True,
                "output_dir": "../escape",
            }
        ],
    )

    payload = plugins.validate_plugins_config(config_path, root_dir=tmp_path / "case")

    assert payload["status"] == "fail"
    assert any("must not contain '..'" in reason for reason in payload["tools"][0]["reasons"])


def test_validate_plugins_config_fails_for_host_control_executable(tmp_path: Path) -> None:
    config_path = _write_plugins_config(
        tmp_path,
        [
            {
                "name": "dangerous_tool",
                "command": ["killall", "Finder"],
                "enabled": True,
                "output_dir": "Plugins_Output/dangerous",
            }
        ],
    )

    payload = plugins.validate_plugins_config(config_path)

    assert payload["status"] == "fail"
    assert any(
        "host-control executable" in reason
        for reason in payload["tools"][0]["reasons"]
    )


def test_validate_plugins_config_fails_for_shell_trampoline(tmp_path: Path) -> None:
    config_path = _write_plugins_config(
        tmp_path,
        [
            {
                "name": "shell_tool",
                "command": ["bash", "-lc", "echo hello"],
                "enabled": True,
                "output_dir": "Plugins_Output/shell",
            }
        ],
    )

    payload = plugins.validate_plugins_config(config_path)

    assert payload["status"] == "fail"
    assert any(
        "shell trampoline executable" in reason
        for reason in payload["tools"][0]["reasons"]
    )


def test_validate_plugins_config_fails_for_env_wrapped_host_control_executable(tmp_path: Path) -> None:
    config_path = _write_plugins_config(
        tmp_path,
        [
            {
                "name": "wrapped_dangerous_tool",
                "command": ["env", "killall", "Finder"],
                "enabled": True,
                "output_dir": "Plugins_Output/wrapped-dangerous",
            }
        ],
    )

    payload = plugins.validate_plugins_config(config_path)

    assert payload["status"] == "fail"
    assert any(
        "host-control executable" in reason
        for reason in payload["tools"][0]["reasons"]
    )


def test_render_plugins_validation_report_uses_validate_payload(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_plugins_config(
        tmp_path,
        [
            {
                "name": "ok_tool",
                "command": ["/bin/echo", "{db_path}"],
                "enabled": True,
                "output_dir": "Plugins_Output/ok",
                "timeout_sec": 30,
            }
        ],
    )

    monkeypatch.setattr(plugins.shutil, "which", lambda _cmd: "/bin/echo")

    payload = plugins.validate_plugins_config(
        config_path,
        root_dir=tmp_path / "case",
        db_path=tmp_path / "case" / "DB_Backup" / "NoteStore.sqlite",
    )
    report = plugins.render_plugins_validation_report(payload)

    assert payload["kind"] == "plugin_contract_v1"
    assert payload["status"] == "ok"
    assert "Contract kind: plugin_contract_v1" in report
    assert "Overall status: ok" in report
    assert "No contract issues detected." in report
