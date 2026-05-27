# -*- coding: utf-8 -*-
"""Logging helpers shared by CLI and engines."""

from __future__ import annotations

import argparse
import atexit
import datetime
import json
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from notes_recovery.io import ensure_dir, require_non_negative_int


LOG_LEVELS = {
    "debug": 10,
    "info": 20,
    "warn": 30,
    "warning": 30,
    "error": 40,
}

DEFAULT_LOG_LEVEL = "info"
DEFAULT_LOG_NAME = "notes_recovery"

ORIGINAL_STDOUT = sys.stdout
ORIGINAL_STDERR = sys.stderr


def _current_timestamp(use_utc: bool) -> datetime.datetime:
    if use_utc:
        return datetime.datetime.now(datetime.timezone.utc)
    return datetime.datetime.now()


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


class LogContext:
    def __init__(self) -> None:
        self.level = LOG_LEVELS[DEFAULT_LOG_LEVEL]
        self.console_level = LOG_LEVELS[DEFAULT_LOG_LEVEL]
        self.quiet = False
        self.file_handle: Optional[object] = None
        self.lock = threading.Lock()
        self.log_path: Optional[Path] = None
        self.max_bytes = 0
        self.backup_count = 0
        self.append = False
        self.time_format = "%Y-%m-%d %H:%M:%S"
        self.use_utc = False
        self.json_enabled = False
        self.command = "run"
        self.session = ""

    def close(self) -> None:
        if self.file_handle:
            try:
                self.file_handle.flush()
                self.file_handle.close()
            except Exception:
                pass
            self.file_handle = None
        self.log_path = None

    def rotate_if_needed(self) -> None:
        if not self.log_path or not self.file_handle:
            return
        if self.max_bytes <= 0 or self.backup_count <= 0:
            return
        try:
            if self.log_path.stat().st_size < self.max_bytes:
                return
        except Exception:
            return
        try:
            self.file_handle.flush()
            self.file_handle.close()
        except Exception:
            pass
        for idx in range(self.backup_count - 1, 0, -1):
            src = self.log_path.with_name(self.log_path.name + f".{idx}")
            dst = self.log_path.with_name(self.log_path.name + f".{idx + 1}")
            if src.exists():
                try:
                    if dst.exists():
                        dst.unlink()
                except Exception:
                    pass
                try:
                    src.rename(dst)
                except Exception:
                    pass
        if self.log_path.exists():
            try:
                first = self.log_path.with_name(self.log_path.name + ".1")
                if first.exists():
                    first.unlink()
                self.log_path.rename(first)
            except Exception:
                pass
        try:
            self.file_handle = self.log_path.open("w", encoding="utf-8")
        except Exception:
            self.file_handle = None


LOG_CONTEXT = LogContext()
LOG_CONTEXT_CONFIGURED = False


class LogTee:
    def __init__(self, stream: object, level_name: str, level_value: int, context: LogContext) -> None:
        self.stream = stream
        self.level_name = level_name
        self.level_value = level_value
        self.context = context
        self.buffer = ""

    def _format(self, line: str) -> str:
        now = _current_timestamp(self.context.use_utc)
        try:
            ts = now.strftime(self.context.time_format)
        except Exception:
            ts = now.strftime("%Y-%m-%d %H:%M:%S")
        return f"[{ts}] {self.level_name.upper():5s} {line}"

    def _format_json(self, line: str) -> str:
        now = _current_timestamp(self.context.use_utc)
        try:
            ts = now.strftime(self.context.time_format)
        except Exception:
            ts = now.strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "ts": ts,
            "level": self.level_name.upper(),
            "message": line,
            "command": self.context.command,
            "session": self.context.session,
            "pid": os.getpid(),
            "thread": threading.current_thread().name,
        }
        return json.dumps(payload, ensure_ascii=True)

    def write(self, text: str) -> int:
        if not text:
            return 0
        if self.stream and (self.level_value >= self.context.console_level):
            self.stream.write(text)
            try:
                self.stream.flush()
            except Exception:
                pass

        if not self.context.file_handle or self.level_value < self.context.level:
            return len(text)

        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            with self.context.lock:
                if self.context.json_enabled:
                    self.context.file_handle.write(self._format_json(line) + "\n")
                else:
                    self.context.file_handle.write(self._format(line) + "\n")
                try:
                    self.context.file_handle.flush()
                except Exception:
                    pass
                self.context.rotate_if_needed()
        return len(text)

    def flush(self) -> None:
        if self.buffer and self.context.file_handle and self.level_value >= self.context.level:
            with self.context.lock:
                if self.context.json_enabled:
                    self.context.file_handle.write(self._format_json(self.buffer))
                    self.context.file_handle.write("\n")
                else:
                    self.context.file_handle.write(self._format(self.buffer))
                    self.context.file_handle.write("\n")
                try:
                    self.context.file_handle.flush()
                except Exception:
                    pass
                self.context.rotate_if_needed()
            self.buffer = ""
        try:
            if self.stream and (self.level_value >= self.context.console_level):
                self.stream.flush()
        except Exception:
            pass


def normalize_log_level(level: Optional[str]) -> int:
    if not level:
        return LOG_LEVELS[DEFAULT_LOG_LEVEL]
    key = level.strip().lower()
    return LOG_LEVELS.get(key, LOG_LEVELS[DEFAULT_LOG_LEVEL])


def resolve_log_path(
    log_file: Optional[str],
    log_dir: Optional[str],
    run_ts: str,
    auto_dir: Optional[Path],
    command: str,
) -> Optional[Path]:
    def build_name(base: Path) -> Path:
        name = f"{DEFAULT_LOG_NAME}_{command}_{run_ts}.log"
        return base / name

    if log_file:
        raw = log_file.strip()
        if raw.lower() == "auto":
            return build_name(auto_dir or Path.cwd())
        path = Path(raw).expanduser()
        raw_str = str(path)
        if "{ts}" in raw_str or "{cmd}" in raw_str:
            raw_str = raw_str.replace("{ts}", run_ts).replace("{cmd}", command)
            return Path(raw_str).expanduser()
        if path.exists() and path.is_dir():
            return build_name(path)
        if raw.endswith(os.sep):
            return build_name(path)
        return path

    if log_dir:
        return build_name(Path(log_dir).expanduser())

    if auto_dir:
        return build_name(auto_dir)

    return None


def setup_cli_logging(args: argparse.Namespace, run_ts: str, auto_dir: Optional[Path], command: str) -> Optional[Path]:
    if args.no_log_file:
        log_path = None
    else:
        log_path = resolve_log_path(args.log_file, args.log_dir, run_ts, auto_dir, command)
    require_non_negative_int(args.log_max_bytes, "log-max-bytes")
    require_non_negative_int(args.log_backup_count, "log-backup-count")
    if args.log_backup_count and args.log_max_bytes <= 0:
        eprint("log-backup-count only applies when log-max-bytes > 0.")
    configure_logging(
        args.log_level,
        log_path,
        args.quiet,
        args.log_append,
        args.log_max_bytes,
        args.log_backup_count,
        time_format=args.log_time_format,
        use_utc=args.log_utc,
        console_level=args.log_console_level,
        json_enabled=args.log_json,
        command=command,
        session=run_ts,
    )
    if log_path:
        print(f"Log file: {log_path}")
    print(
        "Log configuration: "
        f"level={args.log_level} quiet={args.quiet} "
        f"console={args.log_console_level} json={args.log_json} "
        f"utc={args.log_utc} format='{args.log_time_format}' "
        f"rotate={args.log_max_bytes} backups={args.log_backup_count}"
    )
    return log_path


def configure_logging(
    log_level: Optional[str],
    log_file: Optional[Path],
    quiet: bool,
    append: bool,
    max_bytes: int = 0,
    backup_count: int = 0,
    stream_out: Optional[object] = None,
    stream_err: Optional[object] = None,
    time_format: Optional[str] = None,
    use_utc: bool = False,
    console_level: Optional[str] = None,
    json_enabled: bool = False,
    command: str = "run",
    session: str = "",
) -> None:
    global LOG_CONTEXT_CONFIGURED
    LOG_CONTEXT.level = normalize_log_level(log_level)
    LOG_CONTEXT.quiet = quiet
    LOG_CONTEXT.max_bytes = max(0, max_bytes)
    LOG_CONTEXT.backup_count = max(0, backup_count)
    LOG_CONTEXT.append = append
    if time_format:
        LOG_CONTEXT.time_format = time_format
    LOG_CONTEXT.use_utc = use_utc
    LOG_CONTEXT.json_enabled = json_enabled
    LOG_CONTEXT.command = command
    LOG_CONTEXT.session = session
    if quiet:
        LOG_CONTEXT.console_level = LOG_LEVELS["error"]
    else:
        LOG_CONTEXT.console_level = normalize_log_level(console_level)
    LOG_CONTEXT.close()

    if log_file:
        ensure_dir(log_file.parent)
        mode = "a" if append else "w"
        LOG_CONTEXT.file_handle = log_file.open(mode, encoding="utf-8")
        LOG_CONTEXT.log_path = log_file

    if not LOG_CONTEXT_CONFIGURED:
        atexit.register(LOG_CONTEXT.close)
        LOG_CONTEXT_CONFIGURED = True

    out_stream = stream_out if stream_out is not None else ORIGINAL_STDOUT
    err_stream = stream_err if stream_err is not None else ORIGINAL_STDERR
    sys.stdout = LogTee(out_stream, "info", LOG_LEVELS["info"], LOG_CONTEXT)
    sys.stderr = LogTee(err_stream, "error", LOG_LEVELS["error"], LOG_CONTEXT)


def log_debug(message: str) -> None:
    if LOG_CONTEXT.level <= LOG_LEVELS["debug"]:
        print(f"[DEBUG] {message}")


def log_info(message: str) -> None:
    print(message)


def log_warn(message: str) -> None:
    print(message, file=sys.stderr)


def log_error(message: str) -> None:
    print(message, file=sys.stderr)
