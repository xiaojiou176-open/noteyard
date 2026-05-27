from __future__ import annotations

from typing import Optional

from notes_recovery.config import (
    DEFAULT_OUTPUT_ROOT,
    PROTOBUF_MAX_NOTES_DEFAULT,
    PROTOBUF_MAX_ZDATA_MB_DEFAULT,
    SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT,
    SPOTLIGHT_PARSE_MAX_FILES_DEFAULT,
    SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT,
    SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT,
    SPOTLIGHT_PARSE_MIN_STRING_LEN,
)
from notes_recovery.core.pipeline import timestamp_now
from notes_recovery.io import resolve_path
from notes_recovery.services.auto import auto_run


def prompt_text(prompt: str, default: Optional[str], allow_empty: bool) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if not value and default is not None:
            return default
        if not value and not allow_empty:
            print("Please enter a value.")
            continue
        return value


def prompt_yes_no(prompt: str, default: bool) -> bool:
    default_hint = "y/n, default: yes" if default else "y/n, default: no"
    while True:
        value = input(f"{prompt} ({default_hint}): ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please enter y or n.")


def prompt_int(prompt: str, default: int, minimum: int, maximum: int) -> int:
    while True:
        value = input(f"{prompt} [{default}]: ").strip()
        if not value:
            return default
        try:
            parsed = int(value)
            if parsed < minimum or parsed > maximum:
                print(f"Please enter a value between {minimum} and {maximum}.")
                continue
            return parsed
        except ValueError:
            print("Please enter a valid integer.")


def prompt_float(prompt: str, default: float, minimum: float, maximum: float) -> float:
    while True:
        value = input(f"{prompt} [{default}]: ").strip()
        if not value:
            return default
        try:
            parsed = float(value)
            if parsed < minimum or parsed > maximum:
                print(f"Please enter a value between {minimum} and {maximum}.")
                continue
            return parsed
        except ValueError:
            print("Please enter a valid number.")


# =============================================================================

def run_wizard() -> None:
    print("Apple Notes Recovery Wizard (step-by-step)")
    print("Note: this tool only works on copied evidence. Do not open Notes during recovery.")
    print("Tip: keep the defaults first, and only disable slower stages when needed.\n")

    out_dir_str = prompt_text("Snapshot output directory", str(DEFAULT_OUTPUT_ROOT), allow_empty=False)
    base_out_dir = resolve_path(out_dir_str)
    keyword = prompt_text("Keyword (optional, comma/pipe separators supported)", default="", allow_empty=True).strip()
    keyword = keyword or None

    include_core_spotlight = prompt_yes_no("Copy the CoreSpotlight index for fallback search", default=True)
    include_notes_cache = prompt_yes_no("Copy the Notes cache (CloudKit/metadata)", default=True)
    run_wal = prompt_yes_no("Run WAL isolation (best chance right after deletion)", default=True)
    run_query = prompt_yes_no("Run database queries for ghost records", default=True)
    run_carve = prompt_yes_no("Run gzip carving (slower, but deeper)", default=True)
    run_recover = prompt_yes_no("Run sqlite3 .recover for deeper recovery", default=False)
    run_protobuf = prompt_yes_no("Parse ZICNOTEDATA protobuf payloads", default=False)
    run_spotlight_parse = prompt_yes_no("Inspect CoreSpotlight metadata deeply", default=False)
    run_plugins_flag = prompt_yes_no("Run external tools from plugins.json", default=False)
    generate_html_report = prompt_yes_no("Generate an HTML report", default=True)
    run_verify = prompt_yes_no("Run one-shot verification (requires a keyword)", default=False)

    recover_ignore_freelist = False
    recover_lost_and_found = "lost_and_found"
    if run_recover:
        recover_ignore_freelist = prompt_yes_no("Ignore the freelist during recover to reduce noise", default=False)
        recover_lost_and_found = prompt_text("recover table name", default="lost_and_found", allow_empty=False)

    plugins_config = None
    plugins_enable_all = False
    if run_plugins_flag:
        config_raw = prompt_text("Plugin config path (leave empty to use plugins.json in the output directory)", default="", allow_empty=True).strip()
        plugins_config = resolve_path(config_raw) if config_raw else None
        plugins_enable_all = prompt_yes_no("Ignore enabled flags and force all plugins to run", default=False)

    report_out = None
    report_max_items = 50
    if generate_html_report:
        report_max_items = prompt_int("Maximum number of report items", default=50, minimum=5, maximum=500)

    carve_max_hits = 200
    carve_window_size = 2 * 1024 * 1024
    carve_min_text_len = 32
    carve_min_text_ratio = 0.55
    if run_carve:
        carve_max_hits = prompt_int("Maximum carving hit count", default=200, minimum=1, maximum=5000)
        carve_min_text_len = prompt_int("Minimum carved text length", default=32, minimum=8, maximum=2000)
        carve_min_text_ratio = prompt_float("Minimum readable ratio for carved text (0-1)", default=0.55, minimum=0.0, maximum=1.0)

    protobuf_max_notes = PROTOBUF_MAX_NOTES_DEFAULT
    protobuf_max_zdata_mb = PROTOBUF_MAX_ZDATA_MB_DEFAULT
    if run_protobuf:
        protobuf_max_notes = prompt_int("Maximum protobuf record count", default=PROTOBUF_MAX_NOTES_DEFAULT, minimum=1, maximum=5000)
        protobuf_max_zdata_mb = prompt_int("Maximum ZDATA size per protobuf record (MB)", default=PROTOBUF_MAX_ZDATA_MB_DEFAULT, minimum=1, maximum=512)

    spotlight_parse_max_files = SPOTLIGHT_PARSE_MAX_FILES_DEFAULT
    spotlight_parse_max_bytes = SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT
    spotlight_parse_min_string_len = SPOTLIGHT_PARSE_MIN_STRING_LEN
    spotlight_parse_max_string_chars = SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT
    spotlight_parse_max_rows = SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT
    if run_spotlight_parse:
        spotlight_parse_max_files = prompt_int("Maximum Spotlight files to scan", default=SPOTLIGHT_PARSE_MAX_FILES_DEFAULT, minimum=10, maximum=20000)
        spotlight_parse_max_bytes = prompt_int("Maximum Spotlight file size in bytes", default=SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT, minimum=1024, maximum=2 * 1024 * 1024 * 1024)
        spotlight_parse_min_string_len = prompt_int("Minimum Spotlight string length", default=SPOTLIGHT_PARSE_MIN_STRING_LEN, minimum=2, maximum=64)
        spotlight_parse_max_string_chars = prompt_int("Maximum Spotlight string character count per file", default=SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT, minimum=1000, maximum=2_000_000)
        spotlight_parse_max_rows = prompt_int("Maximum Spotlight SQLite row count", default=SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT, minimum=100, maximum=200000)

    verify_top_n = 10
    verify_preview_len = 300
    verify_out = None
    verify_deep = True
    verify_deep_max_mb = 0
    verify_deep_max_hits_per_file = 200
    verify_deep_all = True
    verify_match_all = False
    verify_fuzzy = True
    verify_fuzzy_threshold = 0.72
    verify_fuzzy_boost = 6.0
    verify_fuzzy_max_len = 2000
    if run_verify:
        if not keyword:
            keyword = prompt_text("Verification keyword (required)", default="", allow_empty=False)
        verify_top_n = prompt_int("Verification Top N", default=10, minimum=1, maximum=200)
        verify_preview_len = prompt_int("Verification preview length", default=300, minimum=50, maximum=5000)
        verify_deep = prompt_yes_no("Enable deep scanning", default=True)
        if verify_deep:
            verify_deep_all = prompt_yes_no("Use full deep-scan mode", default=True)
            verify_deep_max_mb = prompt_int("Maximum per-file size for deep scanning (MB, 0 = unlimited)", default=0, minimum=0, maximum=4096)
            verify_deep_max_hits_per_file = prompt_int("Maximum deep-scan hits per file", default=200, minimum=1, maximum=10000)
        verify_match_all = prompt_yes_no("Require all keywords to match", default=False)
        verify_fuzzy = prompt_yes_no("Enable fuzzy matching", default=True)
        if verify_fuzzy:
            verify_fuzzy_threshold = prompt_float("Fuzzy-match threshold (0-1)", default=0.72, minimum=0.0, maximum=1.0)
            verify_fuzzy_boost = prompt_float("Fuzzy-match weight multiplier", default=6.0, minimum=0.0, maximum=100.0)
            verify_fuzzy_max_len = prompt_int("Maximum fuzzy-match comparison length", default=2000, minimum=100, maximum=10000)

    print("\n=== Configuration Summary ===")
    print(f"Output directory: {base_out_dir}")
    print(f"Keyword: {keyword or 'not provided'}")
    print(f"Steps: snapshot={'Y'} wal={run_wal} query={run_query} carve={run_carve} recover={run_recover} "
          f"protobuf={run_protobuf} spotlight-parse={run_spotlight_parse} plugins={run_plugins_flag} "
          f"report={generate_html_report} verify={run_verify}")
    if not prompt_yes_no("Start execution now?", default=True):
        print("Cancelled.")
        return

    run_ts = timestamp_now()
    auto_run(
        base_out_dir,
        keyword,
        include_core_spotlight,
        include_notes_cache,
        run_wal,
        run_query,
        run_carve,
        run_recover,
        recover_ignore_freelist,
        recover_lost_and_found,
        run_plugins_flag,
        plugins_config,
        plugins_enable_all,
        generate_html_report,
        report_out,
        report_max_items,
        carve_max_hits,
        carve_window_size,
        carve_min_text_len,
        carve_min_text_ratio,
        run_protobuf,
        protobuf_max_notes,
        protobuf_max_zdata_mb,
        run_spotlight_parse,
        spotlight_parse_max_files,
        spotlight_parse_max_bytes,
        spotlight_parse_min_string_len,
        spotlight_parse_max_string_chars,
        spotlight_parse_max_rows,
        run_verify,
        verify_top_n,
        verify_preview_len,
        verify_out,
        verify_deep,
        verify_deep_max_mb,
        verify_deep_max_hits_per_file,
        verify_deep_all,
        verify_match_all,
        verify_fuzzy,
        verify_fuzzy_threshold,
        verify_fuzzy_boost,
        verify_fuzzy_max_len,
        run_ts_override=run_ts,
    )


# =============================================================================
