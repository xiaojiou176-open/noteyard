# -*- coding: utf-8 -*-
"""Configuration constants for the Apple Notes forensics toolchain."""

from __future__ import annotations

import re
from pathlib import Path

from notes_recovery.case_contract import (
    CASE_DIR_CACHE_BACKUP,
    CASE_DIR_DB_BACKUP,
    CASE_DIR_PLUGINS_OUTPUT,
    CASE_DIR_RECOVERED_DB,
    CASE_DIR_SPOTLIGHT_BACKUP,
)
from notes_recovery.models import DefaultPaths, FragmentSource, QueryProfileSpec, SchemaType


# =============================================================================
# Core Versions & Defaults
# =============================================================================

QUERY_STRATEGY_VERSION = "2026-01-20.v1"
SPOTLIGHT_PARSE_STRATEGY_VERSION = "2026-01-20.v1"
TIMELINE_STRATEGY_VERSION = "2026-01-20.v1"


DEFAULT_PATHS = DefaultPaths(
    notes_group_container=Path("~/Library/Group Containers/group.com.apple.notes"),
    core_spotlight=Path("~/Library/Metadata/CoreSpotlight"),
    notes_cache=Path("~/Library/Containers/com.apple.Notes/Data/Library/Notes"),
)

# Repo-level path relocation is expected to be safe, but these defaults remain
# intentionally host-bound to macOS Notes evidence locations.
DEFAULT_OUTPUT_ROOT = Path("./output/Notes_Forensics")

DEFAULT_PLUGINS_CONFIG = {
    "tools": [
        {
            "name": "apple_cloud_notes_parser_docker",
            "enabled": False,
            "output_dir": f"{CASE_DIR_PLUGINS_OUTPUT}/apple_cloud_notes_parser",
            "timeout_sec": 900,
            "command": [
                "docker",
                "run",
                "--rm",
                "-v",
                "{db_dir}:/data:ro",
                "-v",
                "{out}:/app/output",
                "ghcr.io/threeplanetssoftware/apple_cloud_notes_parser",
                "-f",
                "/data/NoteStore.sqlite",
                "--html",
            ],
        },
        {
            "name": "sqlite_dissect",
            "enabled": False,
            "output_dir": f"{CASE_DIR_PLUGINS_OUTPUT}/sqlite_dissect",
            "timeout_sec": 900,
            "command": [
                "sqlite_dissect",
                "{db_path}",
                "--output", "{out}",
            ],
        },
        {
            "name": "strings",
            "enabled": False,
            "output_dir": f"{CASE_DIR_PLUGINS_OUTPUT}/strings",
            "timeout_sec": 300,
            "command": [
                "strings",
                "-a",
                "-n", "4",
                "{db_path}",
            ],
        },
        {
            "name": "binwalk",
            "enabled": False,
            "output_dir": f"{CASE_DIR_PLUGINS_OUTPUT}/binwalk",
            "timeout_sec": 600,
            "command": [
                "binwalk",
                "-e",
                "-q",
                "-C", "{out}",
                "{db_path}",
            ],
        },
    ]
}


# =============================================================================
# Case Manifest Defaults (mutable runtime config)
# =============================================================================

CASE_MANIFEST_ENABLED = True
CASE_SIGN_MODE = "none"
CASE_HMAC_KEY = ""
CASE_PGP_KEY = ""
CASE_PGP_HOMEDIR = ""
CASE_PGP_BINARY = "gpg"


# =============================================================================
# Spotlight Parsing
# =============================================================================

GZIP_MAGIC = b"\x1f\x8b\x08"

SPOTLIGHT_PARSE_MAX_FILES_DEFAULT = 240
SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT = 64 * 1024 * 1024
SPOTLIGHT_PARSE_MIN_STRING_LEN = 4
SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT = 120_000
SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT = 2000
SPOTLIGHT_PARSE_BLOB_MAX_BYTES = 2 * 1024 * 1024
SPOTLIGHT_PARSE_MAX_TOP_ITEMS = 120
SPOTLIGHT_PARSE_MAX_MATCHES_PER_FILE = 8000
SPOTLIGHT_QUERY_MAX_LEN = 120
SPOTLIGHT_QUERY_MIN_LEN = 3


# =============================================================================
# Timeline
# =============================================================================

TIMELINE_MAX_EVENTS_DEFAULT = 20000
TIMELINE_MAX_NOTES_DEFAULT = 2000
TIMELINE_MAX_SPOTLIGHT_FILES_DEFAULT = 200
TIMELINE_PREVIEW_MAX_CHARS = 180
TIMELINE_FUTURE_DRIFT_SECONDS = 24 * 3600
TIMELINE_MIN_YEAR = 2001

TIMELINE_DB_CONFIDENCE = 1.0
TIMELINE_WAL_CONFIDENCE = 0.6
TIMELINE_SPOTLIGHT_CONFIDENCE = 0.5
TIMELINE_FS_CONFIDENCE = 0.35


# =============================================================================
# Query Profiles
# =============================================================================

ICLOUD_PROFILE_SPEC = QueryProfileSpec(
    name="icloud",
    schema=SchemaType.ICLOUD,
    required_tables=("ZICCLOUDSYNCINGOBJECT", "ZICNOTEDATA"),
    optional_tables=(),
    table_columns={
        "ZICCLOUDSYNCINGOBJECT": (
            "Z_PK",
            "ZIDENTIFIER",
            "ZTITLE1",
            "ZSNIPPET",
            "ZMARKEDFORDELETION",
            "ZTRASHEDSTATE",
            "ZDELETEDDATE",
            "ZCREATIONDATE",
            "ZMODIFICATIONDATE",
            "ZNOTEDATA",
        ),
        "ZICNOTEDATA": ("Z_PK", "ZDATA"),
    },
)

LEGACY_PROFILE_SPEC = QueryProfileSpec(
    name="legacy",
    schema=SchemaType.LEGACY,
    required_tables=("ZNOTE", "ZNOTEBODY"),
    optional_tables=(),
    table_columns={
        "ZNOTE": ("Z_PK", "ZTITLE", "ZDATEEDITED", "ZCREATIONDATE", "ZMODIFICATIONDATE"),
        "ZNOTEBODY": ("Z_PK", "ZNOTE", "ZHTMLSTRING"),
    },
)


# =============================================================================
# Text Bundle & Recovery
# =============================================================================

TEXT_BUNDLE_TEXT_EXTENSIONS = {
    ".txt",
    ".log",
    ".csv",
    ".json",
    ".jsonl",
    ".md",
    ".html",
    ".htm",
    ".xml",
    ".plist",
    ".sql",
    ".rtf",
    ".tsv",
}
TEXT_BUNDLE_MAX_TEXT_CHARS = 5_000_000
TEXT_BUNDLE_MAX_CSV_ROWS = 200
TEXT_BUNDLE_MAX_MANIFEST_ROWS = 200

RECOVER_MAX_TEXT_CHARS = 8_000_000
RECOVER_STITCH_MIN_OVERLAP = 60
RECOVER_STITCH_MAX_SCAN = 8000
RECOVER_STITCH_MIN_NON_URL_CHARS = 12
RECOVER_MAX_FRAGMENTS_DEFAULT = 1500
RECOVER_MAX_STITCH_ROUNDS_DEFAULT = 5000
STITCH_CLUSTER_JACCARD_THRESHOLD = 0.35
STITCH_CLUSTER_SIGNATURE_SIZE = 64
STITCH_CLUSTER_BUCKET_SIZE = 8
STITCH_CLUSTER_LENGTH_BUCKET = 200
STITCH_CLUSTER_MAX_BUCKET = 300
RECOVER_BINARY_PREVIEW_BYTES = 8192
RECOVER_BINARY_RAW_SLICE_BYTES = 65536
RECOVER_BINARY_STRINGS_MIN_LEN = 4
RECOVER_BINARY_STRINGS_MAX_CHARS = 5_000_000
RECOVER_DEEP_MAX_HITS_PER_FILE_DEFAULT = 2000
RECOVER_TEXT_FILE_PREVIEW_CHARS = 20000
RECOVER_TEXT_FILE_MAX_MB = 20
RECOVER_TEXT_SCAN_DIRS = (
    CASE_DIR_DB_BACKUP,
    CASE_DIR_CACHE_BACKUP,
    CASE_DIR_SPOTLIGHT_BACKUP,
    CASE_DIR_RECOVERED_DB,
)

FRAGMENT_SOURCE_WEIGHTS = {
    FragmentSource.PLUGIN: 1.4,
    FragmentSource.BLOB: 1.1,
    FragmentSource.CSV: 0.7,
    FragmentSource.BINARY: 0.6,
    FragmentSource.TEXT: 0.9,
}

PLUGIN_TEXT_EXTENSIONS = {
    ".txt",
    ".log",
    ".csv",
    ".json",
    ".md",
    ".html",
    ".htm",
    ".xml",
}


# =============================================================================
# WAL Extract
# =============================================================================

WAL_MAGIC_BE = 0x377F0682
WAL_MAGIC_LE = 0x377F0683
WAL_HEADER_SIZE = 32
WAL_FRAME_HEADER_SIZE = 24
WAL_EXTRACT_MAX_FRAMES_DEFAULT = 200000
WAL_EXTRACT_STRINGS_MIN_LEN_DEFAULT = 4
WAL_EXTRACT_STRINGS_MAX_CHARS_DEFAULT = 20000
WAL_DIFF_MAX_FRAMES_DEFAULT = 200000

FREELIST_MAX_PAGES_DEFAULT = 2000
FREELIST_MIN_TEXT_LEN_DEFAULT = 32
FREELIST_MAX_OUTPUT_MB_DEFAULT = 64
FREELIST_STRINGS_MAX_CHARS_DEFAULT = 4000

FSEVENTS_CORRELATION_WINDOW_SEC_DEFAULT = 24 * 3600
FSEVENTS_MAX_RECORDS_DEFAULT = 200000


# =============================================================================
# FTS Index
# =============================================================================

FTS_INDEX_DB_NAME = "fts_index.sqlite"
FTS_INDEX_MAX_FILE_MB_DEFAULT = 64
FTS_INDEX_MAX_DOCS_DEFAULT = 200000
FTS_INDEX_MAX_TEXT_CHARS_DEFAULT = 200000
FTS_INDEX_BATCH_SIZE = 200
FTS_INDEX_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".html",
    ".htm",
    ".log",
    ".sql",
}


# =============================================================================
# Carving
# =============================================================================

CARVE_MAX_OUTPUT_MB_DEFAULT = 16
CARVE_ALGO_DEFAULT = "gzip,zlib,lz4,lzfse"
CARVE_ALGO_ALL = {"gzip", "zlib", "zlib-raw", "lz4", "lzfse"}
LZ4_MAGIC = b"\x04\x22\x4d\x18"
LZ4_MAGIC_LEGACY = b"\x02\x21\x4c\x18"
LZFSE_MAGIC_BLOCKS = (b"bvx1", b"bvx2", b"bvxn", b"bvx-", b"bvx$")


# =============================================================================
# Protobuf
# =============================================================================

PROTOBUF_MAX_NOTES_DEFAULT = 200
PROTOBUF_MAX_ZDATA_MB_DEFAULT = 16
PROTOBUF_EMBEDDED_TYPES = {
    "com.apple.notes.table",
    "com.apple.notes.gallery",
    "com.apple.notes.inlinetextattachment",
}

PROTOBUF_FORMAT_HINT_KEYS = {
    "attributerun",
    "attributeruns",
    "attributes",
    "font",
    "bold",
    "italic",
    "underline",
    "list",
}

PROTOBUF_NOTE_TEXT_MIN_LEN = 40
PROTOBUF_NOTE_TEXT_MAX_CANDIDATES = 8
PROTOBUF_ATTR_RUN_MAX_CANDIDATES = 6
PROTOBUF_URL_MAX_ITEMS = 50
PROTOBUF_ATTACHMENT_MAX_ITEMS = 200
PROTOBUF_UUID_REGEX = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
PROTOBUF_UTI_PREFIXES = ("com.apple.", "public.", "dyn.")


# =============================================================================
# Spotlight Regex
# =============================================================================

SPOTLIGHT_URL_RE = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
SPOTLIGHT_BUNDLE_RE = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}")
SPOTLIGHT_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
SPOTLIGHT_PATH_RE = re.compile(r"/[A-Za-z0-9._~/%+\\\\-]+")
