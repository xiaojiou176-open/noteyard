from __future__ import annotations

import struct
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[12:16] == b"IHDR"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_social_preview_png_has_expected_dimensions() -> None:
    png_path = REPO_ROOT / "assets" / "social" / "social-preview.png"

    assert png_path.exists()
    assert _read_png_dimensions(png_path) == (1280, 640)


def test_social_preview_svg_carries_current_public_story() -> None:
    svg_path = REPO_ROOT / "assets" / "social" / "social-preview.svg"
    svg_text = svg_path.read_text(encoding="utf-8")

    for token in (
        "NotesRecover",
        "Copy-first Apple Notes recovery",
        "bounded AI review",
        "Codex",
        "Claude Code",
        "local MCP",
        "notes-recovery demo",
        "ai-review --demo",
    ):
        assert token in svg_text
