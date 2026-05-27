from pathlib import Path

from notes_recovery.core.scan import classify_binary_target, collect_prefixed_dirs, should_skip_recovery_path


def test_collect_prefixed_dirs(tmp_path: Path) -> None:
    base = tmp_path / "Query_Output_20260101_000000"
    base.mkdir(parents=True)
    dirs = collect_prefixed_dirs(tmp_path, "Query_Output")
    assert base in dirs


def test_should_skip_recovery_path() -> None:
    assert should_skip_recovery_path(Path("Root/Text_Bundle_2026/file.txt"))
    assert should_skip_recovery_path(Path("Root/Recovered_Notes/file.txt"))
    assert should_skip_recovery_path(Path("Root/AI_Review_20260331/triage_summary.md"))


def test_classify_binary_target() -> None:
    source, weight, label = classify_binary_target(Path("NoteStore.sqlite"))
    assert label == "NoteStore"
    assert weight > 0
