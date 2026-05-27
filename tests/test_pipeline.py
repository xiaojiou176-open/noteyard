import json
from pathlib import Path

from notes_recovery.core import pipeline
from notes_recovery.models import PipelineStage, StageResult, StageStatus


def test_build_timestamped_dir_unique(tmp_path: Path) -> None:
    base = tmp_path / "Out"
    ts = "20260101_000000"
    first = pipeline.build_timestamped_dir(base, ts)
    first.mkdir(parents=True)
    second = pipeline.build_timestamped_dir(base, ts)
    assert first != second


def test_run_pipeline_and_summary(tmp_path: Path) -> None:
    def ok_stage():
        return {"ok": True}

    def fail_stage():
        raise RuntimeError("boom")

    stages = [
        PipelineStage("ok", True, True, ok_stage),
        PipelineStage("fail", True, True, fail_stage),
        PipelineStage("skip", True, False, ok_stage),
    ]
    results = pipeline.run_pipeline(stages)
    assert results[0].status == StageStatus.OK
    assert results[1].status == StageStatus.FAILED
    assert len(results) == 2

    summary = pipeline.write_pipeline_summary(tmp_path, "20260101_000000", "test", results, {"k": "v"})
    assert summary.exists()


def test_write_run_manifest(tmp_path: Path) -> None:
    results = [
        StageResult(
            name="stage",
            required=True,
            enabled=True,
            status=StageStatus.OK,
            started_at="2026-01-01T00:00:00",
            ended_at="2026-01-01T00:00:01",
            duration_ms=1000,
            error=None,
            outputs={"out": str(tmp_path)},
        )
    ]
    manifest = pipeline.write_run_manifest(tmp_path, "20260101_000000", "unit", {"k": "v"}, results)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["mode"] == "unit"


def test_finalize_pipeline_writes_review_index(tmp_path: Path) -> None:
    report_path = tmp_path / "report_20260101_000000.html"
    report_path.write_text("report", encoding="utf-8")
    results = [
        StageResult(
            name="report",
            required=False,
            enabled=True,
            status=StageStatus.OK,
            started_at="2026-01-01T00:00:00",
            ended_at="2026-01-01T00:00:01",
            duration_ms=1000,
            error=None,
            outputs={"report_path": str(report_path)},
        )
    ]

    pipeline.finalize_pipeline(tmp_path, "20260101_000000", "unit", {"k": "v"}, results)

    review_index = tmp_path / "review_index.md"
    assert review_index.exists()
    text = review_index.read_text(encoding="utf-8")
    assert "Review Index" in text
    assert "Pipeline summary" in text
    assert "report_20260101_000000.html" in text
    assert "## AI Review" in text
    assert "AI_REVIEW_START" in text
