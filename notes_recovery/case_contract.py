from __future__ import annotations

from pathlib import Path

# Stable top-level case directories.
CASE_DIR_DB_BACKUP = "DB_Backup"
CASE_DIR_CACHE_BACKUP = "Cache_Backup"
CASE_DIR_SPOTLIGHT_BACKUP = "Spotlight_Backup"
CASE_DIR_RECOVERED_DB = "Recovered_DB"
CASE_DIR_RECOVERED_BLOBS = "Recovered_Blobs"
CASE_DIR_RECOVERED_NOTES = "Recovered_Notes"
CASE_DIR_QUERY_OUTPUT = "Query_Output"
CASE_DIR_PROTOBUF_OUTPUT = "Protobuf_Output"
CASE_DIR_PLUGINS_OUTPUT = "Plugins_Output"
CASE_DIR_AI_REVIEW = "AI_Review"
CASE_DIR_SPOTLIGHT_ANALYSIS = "Spotlight_Analysis"
CASE_DIR_TIMELINE = "Timeline"
CASE_DIR_FSEVENTS = "FSEvents"
CASE_DIR_FREELIST_CARVE = "Freelist_Carve"
CASE_DIR_WAL_EXTRACT = "WAL_Extract"
CASE_DIR_WAL_DIFF = "WAL_Diff"
CASE_DIR_WAL_ISOLATION = "WAL_Isolation"
CASE_DIR_BINARY_HITS = "Binary_Hits"
CASE_DIR_META = "Meta"
CASE_DIR_TEXT_BUNDLE = "Text_Bundle"
CASE_DIR_VERIFICATION = "Verification"

# Stable derived variants.
CASE_DIR_QUERY_OUTPUT_RECOVERED = f"{CASE_DIR_QUERY_OUTPUT}_Recovered"
CASE_DIR_RECOVERED_BLOBS_RECOVERED = f"{CASE_DIR_RECOVERED_BLOBS}_Recovered"

# Stable filenames under case roots.
CASE_FILE_NOTESTORE_SQLITE = "NoteStore.sqlite"
CASE_FILE_NOTESTORE_WAL = "NoteStore.sqlite-wal"
CASE_FILE_NOTESTORE_SHM = "NoteStore.sqlite-shm"
CASE_FILE_RECOVERED_NOTESTORE_SQLITE = "NoteStore_recovered.sqlite"

RUN_MANIFEST_STEM = "run_manifest"
CASE_MANIFEST_STEM = "case_manifest"
PIPELINE_SUMMARY_STEM = "pipeline_summary"

# Prefix groups shared across services, public-safe export, and tests.
CASE_ROOT_EVIDENCE_PREFIXES = (
    CASE_DIR_DB_BACKUP,
    CASE_DIR_CACHE_BACKUP,
    CASE_DIR_SPOTLIGHT_BACKUP,
)

CASE_ROOT_DERIVED_PREFIXES = (
    CASE_DIR_RECOVERED_DB,
    CASE_DIR_RECOVERED_BLOBS,
    CASE_DIR_RECOVERED_NOTES,
    CASE_DIR_QUERY_OUTPUT,
    CASE_DIR_PROTOBUF_OUTPUT,
    CASE_DIR_PLUGINS_OUTPUT,
    CASE_DIR_AI_REVIEW,
    CASE_DIR_SPOTLIGHT_ANALYSIS,
    CASE_DIR_TIMELINE,
    CASE_DIR_FSEVENTS,
    CASE_DIR_FREELIST_CARVE,
    CASE_DIR_WAL_EXTRACT,
    CASE_DIR_WAL_DIFF,
    CASE_DIR_BINARY_HITS,
    CASE_DIR_TEXT_BUNDLE,
    CASE_DIR_VERIFICATION,
)

CASE_ROOT_SKIP_SCAN_PREFIXES = (
    CASE_DIR_TEXT_BUNDLE,
    CASE_DIR_RECOVERED_NOTES,
    CASE_DIR_AI_REVIEW,
)

CASE_ROOT_PUBLIC_SAFE_OMITTED_PREFIXES = (
    CASE_DIR_DB_BACKUP,
    CASE_DIR_CACHE_BACKUP,
    CASE_DIR_SPOTLIGHT_BACKUP,
    CASE_DIR_RECOVERED_DB,
    CASE_DIR_RECOVERED_BLOBS,
    CASE_DIR_RECOVERED_NOTES,
    CASE_DIR_PLUGINS_OUTPUT,
    CASE_DIR_AI_REVIEW,
    CASE_DIR_WAL_EXTRACT,
    CASE_DIR_WAL_DIFF,
    CASE_DIR_BINARY_HITS,
    CASE_DIR_TEXT_BUNDLE,
)


def matches_case_prefix(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(f"{prefix}_")


def matches_any_case_prefix(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(matches_case_prefix(name, prefix) for prefix in prefixes)


def case_dir(root_dir: Path, dir_name: str) -> Path:
    return root_dir / dir_name


def prefixed_case_dir_name(prefix: str, run_ts: str) -> str:
    return f"{prefix}_{run_ts}"


def prefixed_case_dir(root_dir: Path, prefix: str, run_ts: str) -> Path:
    return case_dir(root_dir, prefixed_case_dir_name(prefix, run_ts))


def run_manifest_path(root_dir: Path, run_ts: str) -> Path:
    return case_dir(root_dir, f"{RUN_MANIFEST_STEM}_{run_ts}.json")


def case_manifest_path(root_dir: Path, run_ts: str) -> Path:
    return case_dir(root_dir, f"{CASE_MANIFEST_STEM}_{run_ts}.json")


def pipeline_summary_path(root_dir: Path, run_ts: str) -> Path:
    return case_dir(case_dir(root_dir, CASE_DIR_META), f"{PIPELINE_SUMMARY_STEM}_{run_ts}.md")
