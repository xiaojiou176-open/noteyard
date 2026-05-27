from __future__ import annotations

import io
from pathlib import Path

from notes_recovery import logging as nr_logging


def _restore_streams() -> None:
    try:
        nr_logging.sys.stdout.flush()
    except Exception:
        pass
    try:
        nr_logging.sys.stderr.flush()
    except Exception:
        pass
    nr_logging.LOG_CONTEXT.close()
    nr_logging.sys.stdout = nr_logging.ORIGINAL_STDOUT
    nr_logging.sys.stderr = nr_logging.ORIGINAL_STDERR


def test_configure_logging_basic(tmp_path: Path) -> None:
    log_path = tmp_path / "app.log"
    nr_logging.configure_logging(
        log_level="info",
        log_file=log_path,
        quiet=False,
        append=False,
        max_bytes=0,
        backup_count=0,
        time_format="%Y-%m-%d %H:%M:%S",
        use_utc=True,
        console_level="info",
        json_enabled=True,
        command="test",
        session="session",
    )
    nr_logging.log_info("hello")
    nr_logging.log_warn("world " * 20)
    _restore_streams()

    assert log_path.exists()
    data = log_path.read_text(encoding="utf-8")
    assert "hello" in data
    assert "world" in data


def test_log_tee_formats_json(tmp_path: Path) -> None:
    log_path = tmp_path / "json.log"
    buffer_out = io.StringIO()
    buffer_err = io.StringIO()
    nr_logging.configure_logging(
        log_level="info",
        log_file=log_path,
        quiet=False,
        append=False,
        max_bytes=0,
        backup_count=0,
        stream_out=buffer_out,
        stream_err=buffer_err,
        time_format="%H:%M:%S",
        use_utc=False,
        console_level="info",
        json_enabled=True,
        command="json",
        session="case",
    )
    nr_logging.log_info("event")
    nr_logging.log_error("boom")
    _restore_streams()

    content = log_path.read_text(encoding="utf-8")
    assert "event" in content
    assert "boom" in content


def test_logging_rotation(tmp_path: Path) -> None:
    log_path = tmp_path / "rotate.log"
    nr_logging.configure_logging(
        log_level="info",
        log_file=log_path,
        quiet=False,
        append=False,
        max_bytes=64,
        backup_count=1,
        time_format="%Y-%m-%d %H:%M:%S",
        use_utc=True,
        console_level="info",
        json_enabled=True,
        command="rotate",
        session="session",
    )
    nr_logging.log_info("x" * 200)
    _restore_streams()
    rotated = log_path.with_name(log_path.name + ".1")
    assert rotated.exists()


def test_resolve_log_path_and_setup(tmp_path: Path) -> None:
    run_ts = "20260101_000000"
    auto_dir = tmp_path / "auto"
    auto_dir.mkdir()

    path = nr_logging.resolve_log_path("auto", None, run_ts, auto_dir, "cmd")
    assert path and path.parent == auto_dir

    path2 = nr_logging.resolve_log_path("{cmd}_{ts}.log", None, run_ts, None, "run")
    assert path2 and path2.name.startswith("run_20260101_000000")

    args = nr_logging.argparse.Namespace(
        no_log_file=False,
        log_file=str(auto_dir),
        log_dir=None,
        log_max_bytes=0,
        log_backup_count=0,
        log_level="info",
        quiet=False,
        log_append=False,
        log_time_format="%Y-%m-%d %H:%M:%S",
        log_utc=False,
        log_console_level="info",
        log_json=False,
    )
    log_path = nr_logging.setup_cli_logging(args, run_ts, auto_dir, "run")
    _restore_streams()
    assert log_path and log_path.exists()


def test_log_context_rotate_noop(tmp_path: Path) -> None:
    ctx = nr_logging.LogContext()
    ctx.rotate_if_needed()
    ctx.log_path = tmp_path / "noop.log"
    ctx.rotate_if_needed()
    ctx.max_bytes = 0
    ctx.backup_count = 1
    ctx.file_handle = (ctx.log_path).open("w", encoding="utf-8")
    try:
        ctx.rotate_if_needed()
    finally:
        ctx.file_handle.close()

    assert nr_logging.normalize_log_level("missing") == nr_logging.LOG_LEVELS[nr_logging.DEFAULT_LOG_LEVEL]
