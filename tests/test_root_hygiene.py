from pathlib import Path

from scripts.ci.contracts import RUNTIME_HYGIENE_TOKENS
from scripts.ci.check_runtime_hygiene import collect_runtime_hygiene_errors


def test_gitignore_covers_repo_runtime_noise() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    expected_rules = [
        ".agents/",
        ".agent/",
        ".codex/",
        ".claude/",
        ".cursor/",
        ".runtime-cache/",
        "cache/",
        "log/",
        "logs/",
        "*.log",
        "*.egg-info/",
        "output/",
    ]

    for rule in expected_rules:
        assert rule in gitignore


def test_runtime_hygiene_gate_passes_for_minimal_repo(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(
        ".agents/\n.runtime-cache/\ncache/\nlog/\nlogs/\noutput/\nexamples/\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("\n".join(RUNTIME_HYGIENE_TOKENS) + "\n", encoding="utf-8")

    assert collect_runtime_hygiene_errors(tmp_path) == []


def test_runtime_hygiene_gate_detects_examples_noise(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text(
        ".agents/\n.runtime-cache/\ncache/\nlog/\nlogs/\noutput/\nexamples/\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("\n".join(RUNTIME_HYGIENE_TOKENS) + "\n", encoding="utf-8")
    examples = tmp_path / "examples"
    examples.mkdir(parents=True, exist_ok=True)
    (examples / "sample.txt").write_text("noise\n", encoding="utf-8")

    errors = collect_runtime_hygiene_errors(tmp_path)
    assert any("examples/" in error for error in errors)
