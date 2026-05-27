from __future__ import annotations

from pathlib import Path

from scripts.release.check_glama_surface import collect_glama_surface_errors


def test_collect_glama_surface_errors_passes_for_repo_root() -> None:
    errors = collect_glama_surface_errors(Path.cwd())
    assert errors == []
