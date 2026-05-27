from __future__ import annotations

import csv
import datetime
import json
import plistlib
import sqlite3
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Optional

if TYPE_CHECKING:
    from notes_recovery.models import TimelineEvent

from notes_recovery.case_contract import CASE_DIR_SPOTLIGHT_ANALYSIS, case_dir, matches_case_prefix
from notes_recovery.config import (
    SPOTLIGHT_BUNDLE_RE,
    SPOTLIGHT_PARSE_BLOB_MAX_BYTES,
    SPOTLIGHT_PARSE_MAX_MATCHES_PER_FILE,
    SPOTLIGHT_PARSE_MAX_TOP_ITEMS,
    SPOTLIGHT_PARSE_MIN_STRING_LEN,
    SPOTLIGHT_PARSE_STRATEGY_VERSION,
    SPOTLIGHT_PATH_RE,
    SPOTLIGHT_QUERY_MAX_LEN,
    SPOTLIGHT_QUERY_MIN_LEN,
    SPOTLIGHT_URL_RE,
    SPOTLIGHT_UUID_RE,
)
from notes_recovery.core.binary import extract_strings_from_bytes
from notes_recovery.core.pipeline import ensure_unique_file
from notes_recovery.core.sqlite_utils import open_sqlite_readonly
from notes_recovery.core.time_utils import mac_absolute_to_datetime, unix_to_datetime
from notes_recovery.io import ensure_dir, iter_files_safe
from notes_recovery.logging import log_warn
from notes_recovery.models import SpotlightIndexType, SpotlightTokenType
from notes_recovery.utils.bytes import extract_printable_strings


def walk_obj(value: Any, path: str = "root") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_obj(child, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            yield from walk_obj(child, f"{path}[{idx}]")


def format_event_timestamp(ts: datetime.datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_sqlite_header(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            header = f.read(16)
    except Exception:
        return False
    return header.startswith(b"SQLite format 3")


def safe_sqlite_ident(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def classify_spotlight_index_type(path: Path) -> SpotlightIndexType:
    lower = str(path).lower()
    if "cs_default" in lower:
        return SpotlightIndexType.DEFAULT
    if "cs_priority" in lower:
        return SpotlightIndexType.PRIORITY
    return SpotlightIndexType.OTHER


def is_spotlight_deep_candidate(path: Path) -> bool:
    lower = str(path).lower()
    name = path.name.lower()
    if "spotlightknowledgeevents" in lower:
        return True
    if "cs_default" in lower or "cs_priority" in lower:
        return True
    if name.endswith((".db", ".journal", ".toc", ".plist")):
        return True
    if name.startswith(("skg_events", "journalattr", "indexstate")):
        return True
    return False


def normalize_spotlight_timestamp(value: Any) -> Optional[datetime.datetime]:
    if value is None:
        return None
    try:
        numeric = float(value)
    except Exception:
        return None
    if numeric <= 0:
        return None
    if numeric > 1e12:
        return unix_to_datetime(numeric / 1000.0)
    if numeric > 1e10:
        return unix_to_datetime(numeric)
    if numeric > 1e9:
        return unix_to_datetime(numeric)
    if numeric > 1e7:
        return mac_absolute_to_datetime(numeric)
    return None


def is_spotlight_query_candidate(text: str) -> bool:
    if not text:
        return False
    text = text.strip()
    if len(text) < SPOTLIGHT_QUERY_MIN_LEN or len(text) > SPOTLIGHT_QUERY_MAX_LEN:
        return False
    if "://" in text or text.startswith("/"):
        return False
    if SPOTLIGHT_BUNDLE_RE.fullmatch(text) or SPOTLIGHT_UUID_RE.fullmatch(text):
        return False
    alpha_count = sum(ch.isalnum() or "\u4e00" <= ch <= "\u9fff" for ch in text)
    if alpha_count < 3:
        return False
    return True


def harvest_spotlight_tokens(
    text: str,
    counters: dict[SpotlightTokenType, Counter],
    max_matches: int,
) -> None:
    if not text or max_matches <= 0:
        return
    match_count = 0
    for match in SPOTLIGHT_URL_RE.findall(text):
        counters[SpotlightTokenType.URL][match] += 1
        match_count += 1
        if match_count >= max_matches:
            break
    if match_count < max_matches:
        for match in SPOTLIGHT_BUNDLE_RE.findall(text):
            counters[SpotlightTokenType.BUNDLE_ID][match] += 1
            match_count += 1
            if match_count >= max_matches:
                break
    if match_count < max_matches:
        for match in SPOTLIGHT_UUID_RE.findall(text):
            counters[SpotlightTokenType.NOTE_ID][match.lower()] += 1
            match_count += 1
            if match_count >= max_matches:
                break
    if match_count < max_matches:
        for match in SPOTLIGHT_PATH_RE.findall(text):
            if len(match) <= 2:
                continue
            counters[SpotlightTokenType.FILE_PATH][match] += 1
            match_count += 1
            if match_count >= max_matches:
                break

    if match_count < max_matches:
        for line in text.splitlines():
            line = line.strip()
            if is_spotlight_query_candidate(line):
                counters[SpotlightTokenType.QUERY][line] += 1
                match_count += 1
                if match_count >= max_matches:
                    break


def extract_strings_from_value(value: Any, max_chars: int) -> str:
    if value is None or max_chars <= 0:
        return ""
    if isinstance(value, (bytes, bytearray)):
        if len(value) > SPOTLIGHT_PARSE_BLOB_MAX_BYTES:
            return ""
        return extract_strings_from_bytes(bytes(value), SPOTLIGHT_PARSE_MIN_STRING_LEN, max_chars)
    if isinstance(value, str):
        return value[:max_chars]
    return ""


def parse_spotlight_plist(path: Path, counters: dict[SpotlightTokenType, Counter], max_matches: int) -> None:
    try:
        with path.open("rb") as f:
            payload = plistlib.load(f)
    except Exception:
        return
    for _key, value in walk_obj(payload):
        if isinstance(value, str):
            harvest_spotlight_tokens(value, counters, max_matches)


def parse_spotlight_sqlite(
    path: Path,
    counters: dict[SpotlightTokenType, Counter],
    max_matches: int,
    max_rows: int,
    max_value_chars: int,
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str, str, str, str]]]:
    tables_summary: list[tuple[str, str, str]] = []
    events_rows: list[tuple[str, str, str, str, str, str]] = []
    conn = open_sqlite_readonly(path)
    conn.row_factory = sqlite3.Row
    try:
        try:
            table_rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        except Exception:
            return tables_summary, events_rows
        table_names = [row[0] for row in table_rows if row and row[0]]
        for table in table_names:
            try:
                pragma_rows = conn.execute(f"PRAGMA table_info({safe_sqlite_ident(table)})").fetchall()
            except Exception:
                continue
            columns = [row[1] for row in pragma_rows if row and row[1]]
            tables_summary.append((str(path), table, ",".join(columns)))
            if max_rows <= 0:
                continue
            try:
                rows = conn.execute(
                    f"SELECT * FROM {safe_sqlite_ident(table)} LIMIT ?",
                    (max_rows,),
                ).fetchall()
            except Exception:
                continue
            for row in rows:
                note_id = ""
                for col in columns:
                    value = row[col] if col in row.keys() else None
                    col_lower = col.lower()
                    if value is None:
                        continue
                    if not note_id and isinstance(value, str) and (
                        "note" in col_lower or "uuid" in col_lower or "identifier" in col_lower or "uid" in col_lower
                    ):
                        note_id = value
                    if isinstance(value, (int, float)) and any(
                        key in col_lower for key in ("time", "date", "ts", "timestamp", "created", "updated")
                    ):
                        ts = normalize_spotlight_timestamp(value)
                        if ts:
                            events_rows.append(
                                (
                                    format_event_timestamp(ts),
                                    table,
                                    col,
                                    note_id,
                                    str(path),
                                    str(value),
                                )
                            )
                        continue
                    text = extract_strings_from_value(value, max_value_chars)
                    if text:
                        harvest_spotlight_tokens(text, counters, max_matches)
        return tables_summary, events_rows
    finally:
        try:
            conn.close()
        except Exception:
            pass


def collect_spotlight_candidates(
    spotlight_root: Path,
    max_files: int,
    max_bytes: int,
) -> list[Path]:
    if max_files <= 0:
        return []
    candidates: list[tuple[float, Path]] = []
    for path in iter_files_safe(spotlight_root):
        if path.is_symlink():
            continue
        if not is_spotlight_deep_candidate(path):
            continue
        try:
            stat = path.stat()
        except Exception:
            continue
        if max_bytes > 0 and stat.st_size > max_bytes:
            continue
        candidates.append((stat.st_mtime, path))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [path for _mtime, path in candidates[:max_files]]


def write_spotlight_tokens_csv(
    path: Path,
    counters: dict[SpotlightTokenType, Counter],
    max_items: int,
) -> None:
    ensure_dir(path.parent)
    try:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["category", "value", "count"])
            for token_type, counter in counters.items():
                for value, count in counter.most_common(max_items):
                    writer.writerow([token_type.value, value, count])
    except Exception as exc:
        log_warn(f"Failed to write Spotlight token CSV: {path} -> {exc}")


def write_spotlight_events_csv(path: Path, rows: list[tuple[str, str, str, str, str, str]]) -> None:
    ensure_dir(path.parent)
    try:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp_utc", "table", "column", "note_id", "source_path", "raw_value"])
            writer.writerows(rows)
    except Exception as exc:
        log_warn(f"Failed to write Spotlight events CSV: {path} -> {exc}")


def write_spotlight_diagnostics_csv(path: Path, rows: list[tuple[str, str, str, str, str, str]]) -> None:
    ensure_dir(path.parent)
    try:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["path", "index_type", "kind", "size_bytes", "status", "reason"])
            writer.writerows(rows)
    except Exception as exc:
        log_warn(f"Failed to write Spotlight diagnostics CSV: {path} -> {exc}")


def write_spotlight_tables_csv(path: Path, rows: list[tuple[str, str, str]]) -> None:
    ensure_dir(path.parent)
    try:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["db_path", "table", "columns"])
            writer.writerows(rows)
    except Exception as exc:
        log_warn(f"Failed to write Spotlight tables CSV: {path} -> {exc}")


def write_spotlight_access_csv(
    path: Path,
    counters: dict[SpotlightTokenType, Counter],
    max_items: int,
) -> None:
    ensure_dir(path.parent)
    try:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["entity_type", "entity", "count"])
            note_counter = counters.get(SpotlightTokenType.NOTE_ID, Counter())
            if note_counter:
                for value, count in note_counter.most_common(max_items):
                    writer.writerow([SpotlightTokenType.NOTE_ID.value, value, count])
                return
            path_counter = counters.get(SpotlightTokenType.FILE_PATH, Counter())
            if path_counter:
                for value, count in path_counter.most_common(max_items):
                    writer.writerow([SpotlightTokenType.FILE_PATH.value, value, count])
                return
            url_counter = counters.get(SpotlightTokenType.URL, Counter())
            for value, count in url_counter.most_common(max_items):
                writer.writerow([SpotlightTokenType.URL.value, value, count])
    except Exception as exc:
        log_warn(f"Failed to write Spotlight access CSV: {path} -> {exc}")


def write_spotlight_metadata_json(
    path: Path,
    counters: dict[SpotlightTokenType, Counter],
    index_counts: Counter,
    tables: list[tuple[str, str, str]],
    diagnostics_rows: list[tuple[str, str, str, str, str, str]],
    run_ts: str,
) -> None:
    payload = {
        "strategy_version": SPOTLIGHT_PARSE_STRATEGY_VERSION,
        "run_ts": run_ts,
        "files_scanned": len(diagnostics_rows),
        "index_counts": dict(index_counts),
        "search_terms_top": counters[SpotlightTokenType.QUERY].most_common(SPOTLIGHT_PARSE_MAX_TOP_ITEMS),
        "note_access_top": counters[SpotlightTokenType.NOTE_ID].most_common(SPOTLIGHT_PARSE_MAX_TOP_ITEMS),
        "bundle_ids_top": counters[SpotlightTokenType.BUNDLE_ID].most_common(SPOTLIGHT_PARSE_MAX_TOP_ITEMS),
        "file_paths_top": counters[SpotlightTokenType.FILE_PATH].most_common(SPOTLIGHT_PARSE_MAX_TOP_ITEMS),
        "urls_top": counters[SpotlightTokenType.URL].most_common(SPOTLIGHT_PARSE_MAX_TOP_ITEMS),
        "sqlite_tables": [
            {"db_path": row[0], "table": row[1], "columns": row[2].split(",") if row[2] else []}
            for row in tables
        ],
    }
    try:
        ensure_dir(path.parent)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        log_warn(f"Failed to write Spotlight metadata JSON: {path} -> {exc}")


def parse_spotlight_deep(
    root_dir: Path,
    out_dir: Path,
    max_files: int,
    max_bytes: int,
    min_string_len: int,
    max_string_chars: int,
    max_rows_per_table: int,
    run_ts: str,
) -> dict[str, str]:
    spotlight_root = root_dir / "Spotlight_Backup"
    if not spotlight_root.exists():
        log_warn("Spotlight_Backup was not found. Skipping deep CoreSpotlight parsing.")
        return {}
    ensure_dir(out_dir)
    counters = {
        SpotlightTokenType.QUERY: Counter(),
        SpotlightTokenType.BUNDLE_ID: Counter(),
        SpotlightTokenType.FILE_PATH: Counter(),
        SpotlightTokenType.URL: Counter(),
        SpotlightTokenType.NOTE_ID: Counter(),
    }
    index_counts: Counter = Counter()
    diagnostics_rows: list[tuple[str, str, str, str, str, str]] = []
    tables_rows: list[tuple[str, str, str]] = []
    events_rows: list[tuple[str, str, str, str, str, str]] = []

    candidates = collect_spotlight_candidates(spotlight_root, max_files, max_bytes)
    for path in candidates:
        index_type = classify_spotlight_index_type(path)
        index_counts[index_type.value] += 1
        kind = "binary"
        status = "ok"
        reason = ""
        try:
            size = path.stat().st_size
        except Exception:
            size = 0
        try:
            if path.suffix.lower() == ".plist":
                kind = "plist"
                parse_spotlight_plist(path, counters, SPOTLIGHT_PARSE_MAX_MATCHES_PER_FILE)
            elif is_sqlite_header(path):
                kind = "sqlite"
                tables, events = parse_spotlight_sqlite(
                    path,
                    counters,
                    SPOTLIGHT_PARSE_MAX_MATCHES_PER_FILE,
                    max_rows_per_table,
                    max_string_chars,
                )
                tables_rows.extend(tables)
                events_rows.extend(events)
            else:
                kind = "journal"
                text = extract_printable_strings(path, min_string_len, max_string_chars)
                harvest_spotlight_tokens(text, counters, SPOTLIGHT_PARSE_MAX_MATCHES_PER_FILE)
        except Exception as exc:
            status = "error"
            reason = str(exc)
        diagnostics_rows.append(
            (str(path), index_type.value, kind, str(size), status, reason)
        )

    diagnostics_path = ensure_unique_file(out_dir / f"spotlight_diagnostics_{run_ts}.csv")
    tables_path = ensure_unique_file(out_dir / f"spotlight_tables_{run_ts}.csv")
    events_path = ensure_unique_file(out_dir / f"spotlight_events_{run_ts}.csv")
    tokens_path = ensure_unique_file(out_dir / f"spotlight_tokens_{run_ts}.csv")
    access_path = ensure_unique_file(out_dir / f"spotlight_access_{run_ts}.csv")
    metadata_path = ensure_unique_file(out_dir / f"spotlight_metadata_{run_ts}.json")

    write_spotlight_diagnostics_csv(diagnostics_path, diagnostics_rows)
    write_spotlight_tables_csv(tables_path, tables_rows)
    write_spotlight_events_csv(events_path, events_rows)
    write_spotlight_tokens_csv(tokens_path, counters, SPOTLIGHT_PARSE_MAX_TOP_ITEMS)
    write_spotlight_access_csv(access_path, counters, SPOTLIGHT_PARSE_MAX_TOP_ITEMS)
    write_spotlight_metadata_json(metadata_path, counters, index_counts, tables_rows, diagnostics_rows, run_ts)

    return {
        "spotlight_diagnostics": str(diagnostics_path),
        "spotlight_tables": str(tables_path),
        "spotlight_events": str(events_path),
        "spotlight_tokens": str(tokens_path),
        "spotlight_access": str(access_path),
        "spotlight_metadata": str(metadata_path),
    }


def safe_path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except Exception:
        return 0.0


def find_latest_file(base: Path, pattern: str) -> Optional[Path]:
    if not base.exists():
        return None
    candidates = sorted(base.glob(pattern), key=safe_path_mtime, reverse=True)
    return candidates[0] if candidates else None


def find_latest_spotlight_analysis_dir(root_dir: Path) -> Optional[Path]:
    candidates: list[Path] = []
    direct = case_dir(root_dir, CASE_DIR_SPOTLIGHT_ANALYSIS)
    if direct.exists() and direct.is_dir():
        candidates.append(direct)
    if root_dir.exists():
        for path in sorted(root_dir.iterdir()):
            if path.is_dir() and path != direct and matches_case_prefix(path.name, CASE_DIR_SPOTLIGHT_ANALYSIS):
                candidates.append(path)
    if not candidates:
        return None
    return sorted(candidates, key=safe_path_mtime, reverse=True)[0]


def load_json_file(path: Path) -> Optional[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_spotlight_events_csv(path: Path) -> list["TimelineEvent"]:
    from notes_recovery.config import TIMELINE_SPOTLIGHT_CONFIDENCE
    from notes_recovery.models import TimelineEventType, TimelineSource
    from notes_recovery.services.timeline import build_timeline_preview, make_timeline_event

    events: list["TimelineEvent"] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_raw = row.get("timestamp_utc", "")
                if not ts_raw:
                    continue
                try:
                    ts = datetime.datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                except Exception:
                    continue
                note_id = row.get("note_id", "") or ""
                table = row.get("table", "") or ""
                column = row.get("column", "") or ""
                source_path = row.get("source_path", "") or ""
                raw_value = row.get("raw_value", "") or ""
                preview = build_timeline_preview(raw_value)
                event = make_timeline_event(
                    ts,
                    TimelineEventType.INDEXED,
                    TimelineSource.SPOTLIGHT,
                    note_id,
                    "",
                    preview,
                    f"{source_path}::{table}.{column}",
                    TIMELINE_SPOTLIGHT_CONFIDENCE,
                )
                if event:
                    events.append(event)
    except Exception:
        return events
    return events


# =============================================================================
