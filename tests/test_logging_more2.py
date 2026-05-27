from __future__ import annotations

import io
from pathlib import Path

from notes_recovery import logging as nr_logging


def test_log_rotation_and_flush(tmp_path: Path) -> None:
    log_path = tmp_path / "app.log"
    log_path.write_text("x" * 64, encoding="utf-8")
    (tmp_path / "app.log.1").write_text("old", encoding="utf-8")

    ctx = nr_logging.LogContext()
    ctx.log_path = log_path
    ctx.file_handle = log_path.open("a", encoding="utf-8")
    ctx.max_bytes = 8
    ctx.backup_count = 2
    try:
        ctx.rotate_if_needed()
    finally:
        if ctx.file_handle:
            ctx.file_handle.close()

    out = io.StringIO()
    ctx = nr_logging.LogContext()
    ctx.file_handle = (tmp_path / "json.log").open("w", encoding="utf-8")
    ctx.level = 10
    ctx.console_level = 10
    ctx.json_enabled = False

    tee = nr_logging.LogTee(out, "info", 20, ctx)
    tee.write("line1")
    tee.write("\n")
    tee.flush()
    ctx.close()
    assert "line1" in (tmp_path / "json.log").read_text(encoding="utf-8")


def test_resolve_log_path_variants(tmp_path: Path) -> None:
    run_ts = "20260101_000000"
    base_dir = tmp_path / "logs"
    base_dir.mkdir()

    path = nr_logging.resolve_log_path(str(base_dir) + "/", None, run_ts, None, "cmd")
    assert path and path.parent == base_dir

    path2 = nr_logging.resolve_log_path(None, str(base_dir), run_ts, None, "cmd")
    assert path2 and path2.parent == base_dir


def test_log_context_close_and_format_fallback(tmp_path: Path) -> None:
    ctx = nr_logging.LogContext()
    log_path = tmp_path / "close.log"
    ctx.file_handle = log_path.open("w", encoding="utf-8")
    ctx.close()
    assert ctx.file_handle is None

    ctx = nr_logging.LogContext()
    ctx.time_format = None  # type: ignore[assignment]
    ctx.level = 0
    ctx.console_level = 0
    ctx.file_handle = (tmp_path / "fmt.log").open("w", encoding="utf-8")
    tee = nr_logging.LogTee(None, "info", 20, ctx)
    tee.write("line\n")
    ctx.close()
    assert (tmp_path / "fmt.log").exists()
