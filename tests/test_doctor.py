from __future__ import annotations

from pathlib import Path

import notes_recovery.config as config
import notes_recovery.services.doctor as doctor
from notes_recovery.cli.tail_handlers import handle_doctor_command
from notes_recovery.models import DefaultPaths


def test_run_doctor_ready_on_supported_host(tmp_path: Path, monkeypatch) -> None:
    notes = tmp_path / "notes"
    spotlight = tmp_path / "spotlight"
    cache = tmp_path / "cache"
    for path in (notes, spotlight, cache):
        path.mkdir(parents=True)

    monkeypatch.setattr(
        config,
        "DEFAULT_PATHS",
        DefaultPaths(
            notes_group_container=notes,
            core_spotlight=spotlight,
            notes_cache=cache,
        ),
    )
    monkeypatch.setattr(doctor.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(doctor, "_notes_running", lambda: False)
    monkeypatch.setattr(doctor, "_demo_artifacts_available", lambda: True)
    monkeypatch.setattr(config, "DEFAULT_OUTPUT_ROOT", tmp_path / "output" / "Notes_Forensics")

    payload = doctor.run_doctor()

    assert payload["overall_status"] == "ready"
    assert "copied-evidence workflow" in payload["recommended_next_step"]
    assert any(item["name"] == "host-boundary" and item["status"] == "pass" for item in payload["checks"])


def test_run_doctor_reports_demo_only_off_supported_host(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    monkeypatch.setattr(doctor, "_notes_running", lambda: False)
    monkeypatch.setattr(doctor, "_demo_artifacts_available", lambda: True)
    monkeypatch.setattr(config, "DEFAULT_OUTPUT_ROOT", tmp_path / "output" / "Notes_Forensics")

    payload = doctor.run_doctor()

    assert payload["overall_status"] == "demo-only"
    assert "demo" in payload["recommended_next_step"].lower()


def test_handle_doctor_command_can_emit_json(monkeypatch, capsys) -> None:
    payload = {
        "overall_status": "ready",
        "supported_boundary": {
            "host_os": "macOS only",
            "workflow_style": "copy-first local recovery and review",
            "live_store_rule": "do not operate on the original live Notes store",
        },
        "checks": [],
        "optional_extras": {},
        "optional_integrations": {},
        "recommended_next_step": "Run demo first.",
    }

    exit_code = handle_doctor_command(
        type("Args", (), {"json": True})(),
        timestamp_now=lambda: "2026-03-31T00:00:00",
        setup_cli_logging=lambda *_args, **_kwargs: None,
        run_doctor=lambda: payload,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.lstrip().startswith("{")
    assert '"overall_status": "ready"' in captured.out
