from __future__ import annotations

from pathlib import Path

from notes_recovery import logging as nr_logging


class _BadFile:
    def flush(self) -> None:
        raise OSError("flush fail")

    def close(self) -> None:
        raise OSError("close fail")

    def write(self, _data: str) -> int:
        return 0


class _BadStream:
    def __init__(self) -> None:
        self.writes = 0

    def write(self, _data: str) -> int:
        self.writes += 1
        return 0

    def flush(self) -> None:
        raise OSError("stream flush fail")


def test_log_context_close_handles_errors() -> None:
    ctx = nr_logging.LogContext()
    ctx.file_handle = _BadFile()
    ctx.close()
    assert ctx.file_handle is None


def test_log_context_rotate_error_paths(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "app.log"
    log_path.write_text("x" * 64, encoding="utf-8")
    (tmp_path / "app.log.1").write_text("old", encoding="utf-8")
    (tmp_path / "app.log.2").write_text("older", encoding="utf-8")

    ctx = nr_logging.LogContext()
    ctx.log_path = log_path
    ctx.file_handle = _BadFile()
    ctx.max_bytes = 1
    ctx.backup_count = 3

    def boom_unlink(self: Path) -> None:
        raise OSError("unlink fail")

    def boom_rename(self: Path, _dst: Path) -> None:
        raise OSError("rename fail")

    def boom_open(self: Path, *_args, **_kwargs):
        raise OSError("open fail")

    monkeypatch.setattr(Path, "unlink", boom_unlink)
    monkeypatch.setattr(Path, "rename", boom_rename)
    monkeypatch.setattr(Path, "open", boom_open)

    ctx.rotate_if_needed()


def test_log_context_rotate_stat_error(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "stat.log"
    log_path.write_text("x", encoding="utf-8")
    ctx = nr_logging.LogContext()
    ctx.log_path = log_path
    ctx.file_handle = log_path.open("a", encoding="utf-8")
    ctx.max_bytes = 1
    ctx.backup_count = 1

    def boom_stat(self: Path):
        raise OSError("stat fail")

    monkeypatch.setattr(Path, "stat", boom_stat)
    ctx.rotate_if_needed()
    ctx.close()


def test_logtee_write_and_flush_error_paths(tmp_path: Path) -> None:
    ctx = nr_logging.LogContext()
    ctx.file_handle = (tmp_path / "tee.log").open("w", encoding="utf-8")
    ctx.level = 10
    ctx.console_level = 10
    ctx.json_enabled = True
    ctx.time_format = None  # type: ignore[assignment]

    stream = _BadStream()
    tee = nr_logging.LogTee(stream, "info", 20, ctx)
    assert tee.write("") == 0
    tee.write("line")
    tee.write("\n")
    tee.buffer = "tail"
    tee.flush()
    ctx.close()

    assert nr_logging.normalize_log_level(None) == nr_logging.LOG_LEVELS[nr_logging.DEFAULT_LOG_LEVEL]
    assert stream.writes >= 1


def test_resolve_log_path_raw_suffix(tmp_path: Path) -> None:
    run_ts = "20260101_000000"
    path = nr_logging.resolve_log_path(str(tmp_path / "logs") + "/", None, run_ts, None, "cmd")
    assert path and path.name.endswith(".log")
    assert nr_logging.resolve_log_path(None, None, run_ts, None, "cmd") is None
