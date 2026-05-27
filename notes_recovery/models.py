# -*- coding: utf-8 -*-
"""Shared models for the Apple Notes forensics toolchain."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


# =============================================================================
# Enums
# =============================================================================


class SchemaType(Enum):
    ICLOUD = "icloud"
    LEGACY = "legacy"
    UNKNOWN = "unknown"


class WalAction(Enum):
    ISOLATE = "isolate"
    RESTORE = "restore"
    COPY_ONLY = "copy-only"


class ExitCode(Enum):
    OK = 0
    ERROR = 1


class HitSource(Enum):
    CSV = "CSV"
    BLOB = "BLOB"
    BINARY = "BINARY"
    PLUGIN = "PLUGIN"


class FragmentSource(Enum):
    CSV = "CSV"
    BLOB = "BLOB"
    PLUGIN = "PLUGIN"
    BINARY = "BINARY"
    TEXT = "TEXT"


class StageStatus(Enum):
    SKIPPED = "skipped"
    OK = "ok"
    FAILED = "failed"


class TimelineSource(Enum):
    DB = "DB"
    WAL = "WAL"
    SPOTLIGHT = "Spotlight"
    FS = "FS"


class TimelineEventType(Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MARKED_DELETED = "marked_deleted"
    OPENED = "opened"
    VIEWED = "viewed"
    INDEXED = "indexed"
    WAL_MTIME = "wal_mtime"
    WAL_CTIME = "wal_ctime"
    SPOTLIGHT_MTIME = "spotlight_mtime"
    SPOTLIGHT_CTIME = "spotlight_ctime"
    FS_MTIME = "fs_mtime"
    FS_CTIME = "fs_ctime"


class SpotlightIndexType(Enum):
    DEFAULT = "cs_default"
    PRIORITY = "cs_priority"
    OTHER = "other"


class SpotlightTokenType(Enum):
    QUERY = "query"
    BUNDLE_ID = "bundle_id"
    FILE_PATH = "file_path"
    URL = "url"
    NOTE_ID = "note_id"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass(frozen=True)
class DefaultPaths:
    notes_group_container: Path
    core_spotlight: Path
    notes_cache: Path


@dataclass(frozen=True)
class SearchVariant:
    text: str
    weight: float
    label: str


@dataclass(frozen=True)
class PluginTool:
    name: str
    command: list[str]
    enabled: bool
    output_dir: str
    timeout_sec: Optional[int] = None


@dataclass(frozen=True)
class QueryProfileSpec:
    name: str
    schema: SchemaType
    required_tables: tuple[str, ...]
    optional_tables: tuple[str, ...]
    table_columns: dict[str, tuple[str, ...]]


@dataclass
class QueryProfile:
    name: str
    schema: SchemaType
    strategy_version: str
    available_tables: set[str]
    available_columns: dict[str, set[str]]
    missing_tables: dict[str, str]
    missing_columns: dict[str, list[str]]


@dataclass(frozen=True)
class PipelineStage:
    name: str
    required: bool
    enabled: bool
    action: Callable[[], dict[str, Any]]


@dataclass
class StageResult:
    name: str
    required: bool
    enabled: bool
    status: StageStatus
    started_at: str
    ended_at: str
    duration_ms: int
    error: Optional[str]
    outputs: dict[str, Any]
    skip_reason: Optional[str] = None


@dataclass
class TextFragment:
    text: str
    source: FragmentSource
    source_detail: str
    file: str
    occurrences: int
    keyword_hits: int
    length: int
    truncated: bool
    stitchable: bool
    score: float


@dataclass
class BinaryHit:
    path: Path
    offsets: list[int]
    weighted: float
    source_detail: str


@dataclass
class TimelineEvent:
    timestamp: datetime.datetime
    event_type: TimelineEventType
    source: TimelineSource
    note_id: str
    note_title: str
    content_preview: str
    source_detail: str
    confidence: float
    anomaly: bool = False
    anomaly_reason: str = ""


@dataclass
class StitchNode:
    text: str
    fragment_ids: list[int]
    sources: set[str]
    cluster_id: int
    merge_count: int
    overlap_total: int
