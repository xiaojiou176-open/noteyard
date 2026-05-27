from __future__ import annotations

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


def test_setup_cli_logging_no_log_file_and_quiet(monkeypatch) -> None:
    warnings = []

    def fake_eprint(msg: str) -> None:
        warnings.append(msg)

    monkeypatch.setattr(nr_logging, "eprint", fake_eprint)
    args = nr_logging.argparse.Namespace(
        no_log_file=True,
        log_file=None,
        log_dir=None,
        log_max_bytes=0,
        log_backup_count=1,
        log_level="debug",
        quiet=True,
        log_append=False,
        log_time_format="%Y-%m-%d %H:%M:%S",
        log_utc=False,
        log_console_level="info",
        log_json=False,
    )
    nr_logging.setup_cli_logging(args, "20260101_000000", None, "run")
    nr_logging.log_debug("debug")
    _restore_streams()
    assert warnings
