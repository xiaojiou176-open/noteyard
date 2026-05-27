from pathlib import Path

from notes_recovery.cli.parser import build_parser
from notes_recovery.config import DEFAULT_OUTPUT_ROOT
from notes_recovery.services import wizard


def test_default_output_root_uses_ascii_canonical_path() -> None:
    assert DEFAULT_OUTPUT_ROOT == Path("./output/Notes_Forensics")


def test_parser_defaults_follow_ascii_output_root() -> None:
    parser = build_parser()

    snapshot_args = parser.parse_args(["snapshot"])
    assert snapshot_args.out == str(DEFAULT_OUTPUT_ROOT)

    auto_args = parser.parse_args(["auto"])
    assert auto_args.out == str(DEFAULT_OUTPUT_ROOT)

    flatten_args = parser.parse_args(["flatten"])
    assert flatten_args.src == str(DEFAULT_OUTPUT_ROOT)
    assert flatten_args.out == "./output/Notes_Forensics_Flat"


def test_wizard_uses_canonical_default_output_root(monkeypatch) -> None:
    seen_defaults: list[str] = []

    def fake_prompt_text(prompt: str, default: str | None, allow_empty: bool) -> str:
        if prompt == "Snapshot output directory":
            seen_defaults.append(default or "")
            return default or ""
        if prompt == "Keyword (optional, comma/pipe separators supported)":
            return ""
        if prompt == "recover table name":
            return "lost_and_found"
        return default or ""

    def fake_prompt_yes_no(_prompt: str, default: bool) -> bool:
        return False

    monkeypatch.setattr(wizard, "prompt_text", fake_prompt_text)
    monkeypatch.setattr(wizard, "prompt_yes_no", fake_prompt_yes_no)
    monkeypatch.setattr(wizard, "auto_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(wizard, "timestamp_now", lambda: "20260323_000000")

    wizard.run_wizard()

    assert seen_defaults == [str(DEFAULT_OUTPUT_ROOT)]


def test_public_dashboard_entrypoint_has_no_compat_alias() -> None:
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'forensics-dashboard = "notes_recovery.apps.dashboard:main"' in pyproject_text
    assert "notes-dashboard" not in pyproject_text
