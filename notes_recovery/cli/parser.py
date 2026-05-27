from __future__ import annotations

import argparse

from notes_recovery.config import (
    CARVE_ALGO_DEFAULT,
    CARVE_MAX_OUTPUT_MB_DEFAULT,
    DEFAULT_OUTPUT_ROOT,
    FSEVENTS_CORRELATION_WINDOW_SEC_DEFAULT,
    FSEVENTS_MAX_RECORDS_DEFAULT,
    FTS_INDEX_MAX_DOCS_DEFAULT,
    FTS_INDEX_MAX_FILE_MB_DEFAULT,
    FTS_INDEX_MAX_TEXT_CHARS_DEFAULT,
    FREELIST_MAX_OUTPUT_MB_DEFAULT,
    FREELIST_MAX_PAGES_DEFAULT,
    FREELIST_MIN_TEXT_LEN_DEFAULT,
    FREELIST_STRINGS_MAX_CHARS_DEFAULT,
    PROTOBUF_MAX_NOTES_DEFAULT,
    PROTOBUF_MAX_ZDATA_MB_DEFAULT,
    RECOVER_DEEP_MAX_HITS_PER_FILE_DEFAULT,
    RECOVER_MAX_FRAGMENTS_DEFAULT,
    RECOVER_MAX_STITCH_ROUNDS_DEFAULT,
    RECOVER_STITCH_MIN_OVERLAP,
    SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT,
    SPOTLIGHT_PARSE_MAX_FILES_DEFAULT,
    SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT,
    SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT,
    SPOTLIGHT_PARSE_MIN_STRING_LEN,
    TIMELINE_MAX_EVENTS_DEFAULT,
    TIMELINE_MAX_NOTES_DEFAULT,
    TIMELINE_MAX_SPOTLIGHT_FILES_DEFAULT,
    WAL_EXTRACT_MAX_FRAMES_DEFAULT,
    WAL_EXTRACT_STRINGS_MAX_CHARS_DEFAULT,
    WAL_EXTRACT_STRINGS_MIN_LEN_DEFAULT,
    WAL_DIFF_MAX_FRAMES_DEFAULT,
)
from notes_recovery.logging import DEFAULT_LOG_LEVEL, LOG_LEVELS
from notes_recovery.models import WalAction


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="notes-recovery",
        description="Apple Notes forensic recovery toolkit for macOS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Start here:\n"
            "  notes-recovery demo                Zero-risk first look\n"
            "  notes-recovery doctor              Host, boundary, and optional-surface check\n"
            "  notes-recovery ai-review --demo    Synthetic AI-assisted review proof\n"
            "  notes-recovery ask-case --demo ... Evidence-backed synthetic case Q&A\n"
            "\n"
            "Main path:\n"
            "  notes-recovery auto ...            Standard copied-evidence workflow\n"
            "  notes-recovery public-safe-export  Share a redacted review bundle\n"
            "  notes-recovery ai-review --dir ... AI triage on derived review artifacts\n"
            "  notes-recovery ask-case --dir ...  Evidence-backed case question answering\n"
            "\n"
            "Deep analysis and utilities:\n"
            "  query, recover, verify, report, timeline, spotlight-parse, wal-*,\n"
            "  freelist-carve, carve-gzip, protobuf, plugins, plugins-validate,\n"
            "  case-diff, fts-index, flatten, recover-notes, wizard, gui\n"
        ),
    )
    parser.add_argument(
        "--log-level",
        default=DEFAULT_LOG_LEVEL,
        choices=sorted(set(LOG_LEVELS.keys())),
        help="Log level (default: info)",
    )
    parser.add_argument(
        "--log-console-level",
        default=DEFAULT_LOG_LEVEL,
        choices=sorted(set(LOG_LEVELS.keys())),
        help="Console log level (default: info)",
    )
    parser.add_argument(
        "--log-file",
        help="Log file path (supports auto / {ts} / {cmd})",
    )
    parser.add_argument(
        "--log-dir",
        help="Log directory (file name generated automatically)",
    )
    parser.add_argument(
        "--log-append",
        action="store_true",
        help="Append to the log file",
    )
    parser.add_argument(
        "--log-max-bytes",
        type=int,
        default=0,
        help="Maximum log file size in bytes (0 = unlimited)",
    )
    parser.add_argument(
        "--log-backup-count",
        type=int,
        default=0,
        help="Number of rotated log backups (used with log-max-bytes)",
    )
    parser.add_argument(
        "--log-time-format",
        default="%Y-%m-%d %H:%M:%S",
        help="Log timestamp format (strftime)",
    )
    parser.add_argument(
        "--log-utc",
        action="store_true",
        help="Use UTC timestamps in logs",
    )
    parser.add_argument(
        "--log-json",
        action="store_true",
        help="Write log files as JSON lines",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Quiet mode (file logs only; errors still print)",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="Disable log file output",
    )
    parser.add_argument(
        "--case-no-manifest",
        action="store_true",
        help="Disable case manifest output",
    )
    parser.add_argument(
        "--case-sign",
        choices=["none", "hmac", "pgp"],
        default="none",
        help="Case manifest signing mode",
    )
    parser.add_argument(
        "--case-hmac-key",
        help="HMAC key (or use NOTES_CASE_HMAC_KEY)",
    )
    parser.add_argument(
        "--case-pgp-key",
        help="PGP key id (or use NOTES_CASE_PGP_KEY)",
    )
    parser.add_argument(
        "--case-pgp-homedir",
        help="PGP homedir (or use NOTES_CASE_PGP_HOME)",
    )
    parser.add_argument(
        "--case-pgp-binary",
        default="gpg",
        help="PGP binary path",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    snapshot_p = sub.add_parser("snapshot", help="Copy forensic source directories (read-only)")
    snapshot_p.add_argument("--out", default=str(DEFAULT_OUTPUT_ROOT), help="Output root directory (timestamp appended automatically)")
    snapshot_p.add_argument("--include-core-spotlight", action="store_true", help="Include the CoreSpotlight index")
    snapshot_p.add_argument("--include-notes-cache", action="store_true", help="Include the Notes cache")

    wal_p = sub.add_parser("wal-isolate", help="Isolate or restore WAL/SHM files")
    wal_p.add_argument("--dir", required=True, help="Directory containing NoteStore.sqlite")
    wal_p.add_argument(
        "--action",
        required=True,
        choices=[a.value for a in WalAction],
        help="Action type: isolate | restore | copy-only",
    )
    wal_p.add_argument("--isolate-dir", default="WAL_Isolation")
    wal_p.add_argument(
        "--allow-original",
        action="store_true",
        help="Allow changes to the original Notes database (dangerous).",
    )

    wal_extract_p = sub.add_parser("wal-extract", help="Inspect WAL frames deeply and export historical pages")
    wal_extract_p.add_argument("--dir", required=True, help="Output root directory (Notes_Forensics)")
    wal_extract_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    wal_extract_p.add_argument("--wal", help="Use a specific WAL file (optional)")
    wal_extract_p.add_argument("--keyword", help="Keyword filter (affects exports and string extraction only)")
    wal_extract_p.add_argument("--max-frames", type=int, default=WAL_EXTRACT_MAX_FRAMES_DEFAULT, help="Maximum frame count (prevents runaway output)")
    wal_extract_p.add_argument("--page-size", type=int, default=0, help="Override WAL page size (0 = use header value)")
    wal_extract_p.add_argument("--dump-pages", action="store_true", help="Export raw WAL page binaries")
    wal_extract_p.add_argument("--dump-only-duplicates", action="store_true", help="Export duplicate page versions only")
    wal_extract_p.add_argument("--strings", action="store_true", help="Extract page string previews")
    wal_extract_p.add_argument("--strings-min-len", type=int, default=WAL_EXTRACT_STRINGS_MIN_LEN_DEFAULT, help="Minimum string length")
    wal_extract_p.add_argument("--strings-max-chars", type=int, default=WAL_EXTRACT_STRINGS_MAX_CHARS_DEFAULT, help="Maximum string character count")

    wal_diff_p = sub.add_parser("wal-diff", help="Compare two WAL files")
    wal_diff_p.add_argument("--wal-a", required=True, help="WAL file A")
    wal_diff_p.add_argument("--wal-b", required=True, help="WAL file B")
    wal_diff_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    wal_diff_p.add_argument("--page-size", type=int, default=0, help="Override WAL page size (0 = use header value)")
    wal_diff_p.add_argument("--max-frames", type=int, default=WAL_DIFF_MAX_FRAMES_DEFAULT, help="Maximum frame count (prevents runaway output)")

    freelist_p = sub.add_parser("freelist-carve", help="Carve residual text from the SQLite freelist")
    freelist_p.add_argument("--db", required=True, help="Path to NoteStore.sqlite")
    freelist_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    freelist_p.add_argument("--keyword", help="Keyword filter")
    freelist_p.add_argument("--min-text-len", type=int, default=FREELIST_MIN_TEXT_LEN_DEFAULT, help="Minimum text length filter")
    freelist_p.add_argument("--max-pages", type=int, default=FREELIST_MAX_PAGES_DEFAULT, help="Maximum freelist page count")
    freelist_p.add_argument("--max-output-mb", type=int, default=FREELIST_MAX_OUTPUT_MB_DEFAULT, help="Maximum output size (MB)")
    freelist_p.add_argument("--strings-max-chars", type=int, default=FREELIST_STRINGS_MAX_CHARS_DEFAULT, help="Maximum string character count")

    fsevents_p = sub.add_parser("fsevents-correlate", help="Correlate FSEvents with Spotlight events")
    fsevents_p.add_argument("--dir", help="Output root directory (Notes_Forensics, used to auto-locate Spotlight_Analysis)")
    fsevents_p.add_argument("--fsevents", required=True, help="FSEvents CSV/JSON/JSONL file")
    fsevents_p.add_argument("--spotlight-events", help="Spotlight events CSV (optional)")
    fsevents_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    fsevents_p.add_argument("--window-sec", type=int, default=FSEVENTS_CORRELATION_WINDOW_SEC_DEFAULT, help="Matching time window in seconds")
    fsevents_p.add_argument("--max-records", type=int, default=FSEVENTS_MAX_RECORDS_DEFAULT, help="Maximum parsed record count")

    fts_p = sub.add_parser("fts-index", help="Build a full-text search index (FTS5) for recovered outputs")
    fts_p.add_argument("--dir", required=True, help="Output root directory (Notes_Forensics)")
    fts_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    fts_p.add_argument("--keyword", help="Index only content containing the keyword (optional)")
    fts_p.add_argument("--source", choices=["notes", "db", "all"], default="all", help="Index source")
    fts_p.add_argument("--db", help="Recovered_DB sqlite path (optional)")
    fts_p.add_argument("--db-table", help="Index this table name (optional)")
    fts_p.add_argument("--db-columns", help="Index these columns (comma-separated)")
    fts_p.add_argument("--db-title-column", help="Title column to display (optional)")
    fts_p.add_argument("--max-docs", type=int, default=FTS_INDEX_MAX_DOCS_DEFAULT, help="Maximum indexed document count")
    fts_p.add_argument("--max-file-mb", type=int, default=FTS_INDEX_MAX_FILE_MB_DEFAULT, help="Maximum per-file size (MB)")
    fts_p.add_argument("--max-text-chars", type=int, default=FTS_INDEX_MAX_TEXT_CHARS_DEFAULT, help="Maximum per-document character count")

    query_p = sub.add_parser("query", help="Run forensic queries and export CSV results")
    query_p.add_argument("--db", required=True, help="Path to NoteStore.sqlite")
    query_p.add_argument("--keyword", help="Keyword used for summary search")
    query_p.add_argument("--out", help="Output directory (timestamp appended automatically)")

    carve_p = sub.add_parser("carve-gzip", help="Carve compressed payload blocks from the database (gzip/zlib/lz4/lzfse)")
    carve_p.add_argument("--db", required=True, help="Path to NoteStore.sqlite")
    carve_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    carve_p.add_argument("--keyword", help="Keyword filter")
    carve_p.add_argument("--max-hits", type=int, default=500, help="Maximum hit count")
    carve_p.add_argument("--window-size", type=int, default=2 * 1024 * 1024, help="Decompression window size in bytes")
    carve_p.add_argument("--min-text-len", type=int, default=32, help="Minimum text length filter")
    carve_p.add_argument("--min-text-ratio", type=float, default=0.55, help="Minimum readable ratio (0-1)")
    carve_p.add_argument("--algorithms", default=CARVE_ALGO_DEFAULT, help="Carving algorithms (comma-separated, all = everything)")
    carve_p.add_argument("--max-output-mb", type=int, default=CARVE_MAX_OUTPUT_MB_DEFAULT, help="Maximum decompressed output size (MB)")

    recover_p = sub.add_parser("recover", help="Generate a recovered database with sqlite3 .recover")
    recover_p.add_argument("--db", required=True, help="Path to NoteStore.sqlite")
    recover_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    recover_p.add_argument("--ignore-freelist", action="store_true", help="Ignore the freelist to reduce noise")
    recover_p.add_argument("--lost-and-found", default="lost_and_found", help="Recovered table name")

    plugins_p = sub.add_parser("plugins", help="Run external tools defined in plugins.json")
    plugins_p.add_argument("--dir", required=True, help="Output root directory (Notes_Forensics)")
    plugins_p.add_argument("--db", help="Path to NoteStore.sqlite (defaults to DB_Backup)")
    plugins_p.add_argument("--config", help="Plugin config path (defaults to plugins.json in the output directory)")
    plugins_p.add_argument("--enable-all", action="store_true", help="Ignore enabled flags and force all plugins to run")
    plugins_validate_p = sub.add_parser(
        "plugins-validate",
        help="Validate the plugin contract, placeholder commands, and local tool availability",
    )
    plugins_validate_p.add_argument("--dir", help="Existing case root directory used for path rendering (optional)")
    plugins_validate_p.add_argument("--db", help="Path to NoteStore.sqlite used for command rendering (optional)")
    plugins_validate_p.add_argument("--config", required=True, help="Plugin config path to validate")
    plugins_validate_p.add_argument("--json", action="store_true", help="Print the validation payload as JSON")

    flatten_p = sub.add_parser("flatten", help="Flatten the output directory into a single-layer backup")
    flatten_p.add_argument("--src", default=str(DEFAULT_OUTPUT_ROOT), help="Source directory (default: output/Notes_Forensics)")
    flatten_p.add_argument("--out", default="./output/Notes_Forensics_Flat", help="Flattened output directory (timestamp appended automatically)")
    flatten_p.add_argument("--no-manifest", action="store_true", help="Do not generate flatten_manifest.csv")

    auto_p = sub.add_parser("auto", help="Run the automated end-to-end workflow (non-interactive)")
    auto_p.add_argument("--out", default=str(DEFAULT_OUTPUT_ROOT), help="Output root directory (timestamp appended automatically)")
    auto_p.add_argument("--keyword", help="Keyword filter (comma or pipe separators supported)")
    auto_p.add_argument("--skip-core-spotlight", action="store_true", help="Skip CoreSpotlight copying")
    auto_p.add_argument("--skip-notes-cache", action="store_true", help="Skip Notes cache copying")
    auto_p.add_argument("--skip-wal", action="store_true", help="Skip WAL isolation")
    auto_p.add_argument("--skip-query", action="store_true", help="Skip database queries")
    auto_p.add_argument("--skip-carve", action="store_true", help="Skip physical carving")
    auto_p.add_argument("--recover", action="store_true", help="Run sqlite3 .recover for deeper recovery")
    auto_p.add_argument("--recover-ignore-freelist", action="store_true", help="Ignore the freelist during recovery to reduce noise")
    auto_p.add_argument("--recover-lost-and-found", default="lost_and_found", help="Recovered table name")
    auto_p.add_argument("--plugins", action="store_true", help="Run external tools defined in plugins.json")
    auto_p.add_argument("--plugins-config", help="External-tool config path (defaults to plugins.json in the output directory)")
    auto_p.add_argument("--plugins-enable-all", action="store_true", help="Ignore enabled flags and force all plugins to run")
    auto_p.add_argument("--report", action="store_true", help="Generate an HTML report")
    auto_p.add_argument("--report-out", help="Custom report output path (timestamp appended automatically)")
    auto_p.add_argument("--report-max-items", type=int, default=50, help="Maximum item count shown in the report")
    auto_p.add_argument("--carve-max-hits", type=int, default=200, help="Maximum carving hit count")
    auto_p.add_argument("--carve-window-size", type=int, default=2 * 1024 * 1024, help="Carving decompression window size in bytes")
    auto_p.add_argument("--carve-min-text-len", type=int, default=32, help="Minimum carved text length filter")
    auto_p.add_argument("--carve-min-text-ratio", type=float, default=0.55, help="Minimum readable ratio for carved text (0-1)")
    auto_p.add_argument("--protobuf", action="store_true", help="Parse ZICNOTEDATA protobuf payloads for structured recovery")
    auto_p.add_argument("--protobuf-max-notes", type=int, default=PROTOBUF_MAX_NOTES_DEFAULT, help="Maximum protobuf note count")
    auto_p.add_argument("--protobuf-max-zdata-mb", type=int, default=PROTOBUF_MAX_ZDATA_MB_DEFAULT, help="Maximum ZDATA size per protobuf record (MB)")
    auto_p.add_argument("--spotlight-parse", action="store_true", help="Inspect CoreSpotlight metadata deeply")
    auto_p.add_argument("--spotlight-parse-max-files", type=int, default=SPOTLIGHT_PARSE_MAX_FILES_DEFAULT, help="Maximum Spotlight files to scan")
    auto_p.add_argument("--spotlight-parse-max-bytes", type=int, default=SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT, help="Maximum per-file Spotlight size in bytes")
    auto_p.add_argument("--spotlight-parse-min-string-len", type=int, default=SPOTLIGHT_PARSE_MIN_STRING_LEN, help="Minimum Spotlight string length")
    auto_p.add_argument("--spotlight-parse-max-string-chars", type=int, default=SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT, help="Maximum Spotlight string character count per file")
    auto_p.add_argument("--spotlight-parse-max-rows", type=int, default=SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT, help="Maximum Spotlight SQLite row count")
    auto_p.add_argument("--verify", action="store_true", help="Run one-shot verification (requires a keyword)")
    auto_p.add_argument("--verify-top", type=int, default=10, help="Number of Top-N verification results")
    auto_p.add_argument("--verify-preview-len", type=int, default=300, help="Verification preview length in characters")
    auto_p.add_argument("--verify-out", help="Verification output directory (timestamp appended automatically)")
    auto_p.add_argument("--verify-no-deep", action="store_true", help="Limit verification to CSV and fragment scans only (skip deep scanning)")
    auto_p.add_argument("--verify-deep-max-mb", type=int, default=0, help="Maximum per-file size for deep scanning in MB (0 = unlimited)")
    auto_p.add_argument("--verify-deep-max-hits-per-file", type=int, default=200, help="Maximum deep-scan hits per file")
    auto_p.add_argument("--verify-deep-core-only", action="store_true", help="Limit deep verification to core files only")
    auto_p.add_argument("--verify-match-all", action="store_true", help="Require all keywords to match")
    auto_p.add_argument("--verify-no-fuzzy", action="store_true", help="Disable fuzzy matching")
    auto_p.add_argument("--verify-fuzzy-threshold", type=float, default=0.72, help="Fuzzy-match threshold (0-1)")
    auto_p.add_argument("--verify-fuzzy-boost", type=float, default=6.0, help="Fuzzy-match weight multiplier")
    auto_p.add_argument("--verify-fuzzy-max-len", type=int, default=2000, help="Maximum fuzzy-match comparison length")

    sub.add_parser("demo", help="Show the zero-risk public-safe demo surface and sample artifacts")
    doctor_p = sub.add_parser("doctor", help="Check host boundary, baseline readiness, and optional surfaces")
    doctor_p.add_argument(
        "--json",
        action="store_true",
        help="Print the doctor result as JSON instead of the human-readable report",
    )
    ai_review_p = sub.add_parser(
        "ai-review",
        help="Generate AI-assisted triage from review artifacts or the synthetic demo surface",
    )
    ai_review_p.add_argument("--dir", help="Existing case root directory")
    ai_review_p.add_argument("--demo", action="store_true", help="Use the bundled synthetic demo artifacts instead of a real case root")
    ai_review_p.add_argument(
        "--provider",
        choices=["mock", "ollama", "openai"],
        help="AI provider to use (`mock` is for demo/testing, `ollama` is the real local provider, `openai` is explicit cloud opt-in)",
    )
    ai_review_p.add_argument("--model", help="Model name for the selected provider")
    ai_review_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    ai_review_p.add_argument("--ollama-base-url", help="Override the local Ollama base URL")
    ai_review_p.add_argument("--openai-api-key", help="Override the OpenAI API key for this run")
    ai_review_p.add_argument(
        "--allow-cloud",
        action="store_true",
        help="Explicitly allow the cloud-backed OpenAI provider for this run",
    )
    ai_review_p.add_argument("--timeout-sec", type=int, default=120, help="Provider request timeout in seconds")
    ask_case_p = sub.add_parser(
        "ask-case",
        help="Ask an evidence-backed question about a case root or the synthetic demo review surface",
    )
    ask_case_p.add_argument("--dir", help="Existing case root directory")
    ask_case_p.add_argument("--demo", action="store_true", help="Use the bundled synthetic demo artifacts instead of a real case root")
    ask_case_p.add_argument("--question", required=True, help="Question to answer from derived case artifacts")
    ask_case_p.add_argument(
        "--provider",
        choices=["mock", "ollama", "openai"],
        help="AI provider to use (`mock` is for demo/testing, `ollama` is the real local provider, `openai` is explicit cloud opt-in)",
    )
    ask_case_p.add_argument("--model", help="Model name for the selected provider")
    ask_case_p.add_argument("--ollama-base-url", help="Override the local Ollama base URL")
    ask_case_p.add_argument("--openai-api-key", help="Override the OpenAI API key for this run")
    ask_case_p.add_argument(
        "--allow-cloud",
        action="store_true",
        help="Explicitly allow the cloud-backed OpenAI provider for this run",
    )
    ask_case_p.add_argument("--timeout-sec", type=int, default=120, help="Provider request timeout in seconds")
    ask_case_p.add_argument("--json", action="store_true", help="Print the ask-case result as JSON")
    case_diff_p = sub.add_parser(
        "case-diff",
        help="Compare two case roots at the manifest/review-artifact layer",
    )
    case_diff_p.add_argument("--dir-a", required=True, help="First case root")
    case_diff_p.add_argument("--dir-b", required=True, help="Second case root")
    case_diff_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    case_diff_p.add_argument("--json", action="store_true", help="Print the diff payload as JSON after writing outputs")

    public_safe_p = sub.add_parser(
        "public-safe-export",
        help="Export a redacted public-safe bundle from an existing case root",
    )
    public_safe_p.add_argument("--dir", required=True, help="Existing case root directory")
    public_safe_p.add_argument("--out", required=True, help="Output directory for the redacted bundle (timestamp appended automatically)")

    report_p = sub.add_parser("report", help="Generate an HTML report from recovered outputs")
    report_p.add_argument("--dir", required=True, help="Output root directory (Notes_Forensics)")
    report_p.add_argument("--keyword", help="Keyword highlighting")
    report_p.add_argument("--out", help="HTML output path (timestamp appended automatically)")
    report_p.add_argument("--max-items", type=int, default=50, help="Maximum item count shown in the report")

    verify_p = sub.add_parser("verify", help="Run one-shot verification and show a Top-10 overview")
    verify_p.add_argument("--dir", required=True, help="Output root directory (Notes_Forensics)")
    verify_p.add_argument("--keyword", required=True, help="Keyword is required (comma or pipe separators supported)")
    verify_p.add_argument("--top", type=int, default=10, help="Number of Top-N results")
    verify_p.add_argument("--preview-len", type=int, default=300, help="Preview length in characters")
    verify_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    verify_p.add_argument("--no-deep", action="store_true", help="Scan CSV and fragments only (skip deep scanning)")
    verify_p.add_argument("--deep-max-mb", type=int, default=0, help="Maximum per-file size for deep scanning in MB (0 = unlimited)")
    verify_p.add_argument("--deep-max-hits-per-file", type=int, default=200, help="Maximum deep-scan hits per file")
    verify_p.add_argument("--deep-core-only", action="store_true", help="Limit deep scanning to core files only")
    verify_p.add_argument("--match-all", action="store_true", help="Require all keywords to match")
    verify_p.add_argument("--no-fuzzy", action="store_true", help="Disable fuzzy matching")
    verify_p.add_argument("--fuzzy-threshold", type=float, default=0.72, help="Fuzzy-match threshold (0-1)")
    verify_p.add_argument("--fuzzy-boost", type=float, default=6.0, help="Fuzzy-match weight multiplier")
    verify_p.add_argument("--fuzzy-max-len", type=int, default=2000, help="Maximum fuzzy-match comparison length")

    protobuf_p = sub.add_parser("protobuf", help="Parse ZICNOTEDATA protobuf payloads")
    protobuf_p.add_argument("--db", required=True, help="Path to NoteStore.sqlite")
    protobuf_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    protobuf_p.add_argument("--keyword", help="Title or summary keyword filter")
    protobuf_p.add_argument("--max-notes", type=int, default=PROTOBUF_MAX_NOTES_DEFAULT, help="Maximum parsed record count")
    protobuf_p.add_argument("--max-zdata-mb", type=int, default=PROTOBUF_MAX_ZDATA_MB_DEFAULT, help="Maximum ZDATA size per record (MB)")

    timeline_p = sub.add_parser("timeline", help="Rebuild a multi-source timeline and correlate events")
    timeline_p.add_argument("--dir", required=True, help="Output root directory (Notes_Forensics)")
    timeline_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    timeline_p.add_argument("--keyword", help="Keyword filter (comma or pipe separators supported)")
    timeline_p.add_argument("--max-notes", type=int, default=TIMELINE_MAX_NOTES_DEFAULT, help="Maximum number of parsed notes")
    timeline_p.add_argument("--max-events", type=int, default=TIMELINE_MAX_EVENTS_DEFAULT, help="Maximum number of output events")
    timeline_p.add_argument("--spotlight-max-files", type=int, default=TIMELINE_MAX_SPOTLIGHT_FILES_DEFAULT, help="Maximum number of Spotlight files to scan")
    timeline_p.add_argument("--no-plotly", action="store_true", help="Disable Plotly visualization output")
    timeline_p.add_argument("--no-fs", action="store_true", help="Disable filesystem timestamp collection")

    spotlight_p = sub.add_parser("spotlight-parse", help="Inspect CoreSpotlight metadata deeply")
    spotlight_p.add_argument("--dir", required=True, help="Output root directory (Notes_Forensics)")
    spotlight_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    spotlight_p.add_argument("--max-files", type=int, default=SPOTLIGHT_PARSE_MAX_FILES_DEFAULT, help="Maximum number of scanned files")
    spotlight_p.add_argument("--max-bytes", type=int, default=SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT, help="Maximum per-file size in bytes")
    spotlight_p.add_argument("--min-string-len", type=int, default=SPOTLIGHT_PARSE_MIN_STRING_LEN, help="Minimum extracted string length")
    spotlight_p.add_argument("--max-string-chars", type=int, default=SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT, help="Maximum extracted string character count per file")
    spotlight_p.add_argument("--max-rows-per-table", type=int, default=SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT, help="Maximum SQLite rows scanned per table")

    recover_notes_p = sub.add_parser("recover-notes", help="Recover and stitch notes by keyword")
    recover_notes_p.add_argument("--dir", required=True, help="Output root directory (Notes_Forensics)")
    recover_notes_p.add_argument("--keyword", required=True, help="Keyword or URL (comma or pipe separators supported)")
    recover_notes_p.add_argument("--out", help="Output directory (timestamp appended automatically)")
    recover_notes_p.add_argument("--min-overlap", type=int, default=RECOVER_STITCH_MIN_OVERLAP, help="Minimum stitch overlap length")
    recover_notes_p.add_argument("--max-fragments", type=int, default=RECOVER_MAX_FRAGMENTS_DEFAULT, help="Maximum number of fragments used for stitching")
    recover_notes_p.add_argument("--max-stitch-rounds", type=int, default=RECOVER_MAX_STITCH_ROUNDS_DEFAULT, help="Maximum stitch round count")
    recover_notes_p.add_argument("--no-deep", action="store_true", help="Disable deep-scan previews")
    recover_notes_p.add_argument("--no-deep-all", action="store_true", help="Limit deep scanning to core files only")
    recover_notes_p.add_argument("--deep-max-mb", type=int, default=0, help="Maximum per-file size for deep scanning in MB (0 = unlimited)")
    recover_notes_p.add_argument("--deep-max-hits-per-file", type=int, default=RECOVER_DEEP_MAX_HITS_PER_FILE_DEFAULT, help="Maximum deep-scan hits per file")
    recover_notes_p.add_argument("--match-all", action="store_true", help="Require all keywords to match")
    recover_notes_p.add_argument("--no-binary-copy", action="store_true", help="Do not copy matched binary files")
    recover_notes_p.add_argument("--binary-copy-max-mb", type=int, default=0, help="Maximum copied binary file size in MB (0 = unlimited)")

    sub.add_parser("wizard", help="Run the step-by-step wizard")
    sub.add_parser("gui", help="Launch the simplified GUI")

    return parser
