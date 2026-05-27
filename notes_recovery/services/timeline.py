from __future__ import annotations

import csv
import datetime
import html
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

from notes_recovery.case_contract import (
    CASE_DIR_DB_BACKUP,
    CASE_DIR_RECOVERED_DB,
    CASE_DIR_SPOTLIGHT_ANALYSIS,
    CASE_DIR_SPOTLIGHT_BACKUP,
    CASE_DIR_WAL_ISOLATION,
    CASE_FILE_NOTESTORE_SHM,
    CASE_FILE_NOTESTORE_SQLITE,
    CASE_FILE_NOTESTORE_WAL,
    CASE_FILE_RECOVERED_NOTESTORE_SQLITE,
    case_dir,
    matches_case_prefix,
)
from notes_recovery.config import (
    ICLOUD_PROFILE_SPEC,
    LEGACY_PROFILE_SPEC,
    SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT,
    SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT,
    SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT,
    SPOTLIGHT_PARSE_MIN_STRING_LEN,
    TIMELINE_DB_CONFIDENCE,
    TIMELINE_FS_CONFIDENCE,
    TIMELINE_FUTURE_DRIFT_SECONDS,
    TIMELINE_MIN_YEAR,
    TIMELINE_PREVIEW_MAX_CHARS,
    TIMELINE_SPOTLIGHT_CONFIDENCE,
    TIMELINE_STRATEGY_VERSION,
    TIMELINE_WAL_CONFIDENCE,
)
from notes_recovery.core.pipeline import ensure_unique_file
from notes_recovery.core.keywords import choose_best_text_preview, keyword_matches_any, split_keywords
from notes_recovery.core.sqlite_utils import (
    build_query_profile,
    detect_schema,
    escape_like,
    open_sqlite_readonly,
)
from notes_recovery.io import ensure_dir, iter_files_safe
from notes_recovery.logging import log_warn
from notes_recovery.models import (
    SchemaType,
    TimelineEvent,
    TimelineEventType,
    TimelineSource,
)
from notes_recovery.services.report import highlight
from notes_recovery.services.spotlight import (
    load_json_file,
    load_spotlight_events_csv,
    parse_spotlight_deep,
)
from notes_recovery.utils.text import html_to_text, normalize_whitespace


def find_latest_file(root_dir: Path, pattern: str) -> Optional[Path]:
    candidates = list(root_dir.rglob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime, default=None)


def find_latest_spotlight_analysis_dir(root_dir: Path) -> Optional[Path]:
    if not root_dir.exists():
        return None
    candidates = [p for p in root_dir.iterdir() if p.is_dir() and matches_case_prefix(p.name, CASE_DIR_SPOTLIGHT_ANALYSIS)]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime, default=None)


def mac_absolute_to_datetime(value: Optional[float]) -> Optional[datetime.datetime]:
    if value is None:
        return None
    try:
        seconds = float(value)
    except Exception:
        return None
    base = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)
    try:
        return base + datetime.timedelta(seconds=seconds)
    except Exception:
        return None


def unix_to_datetime(value: Optional[float]) -> Optional[datetime.datetime]:
    if value is None:
        return None
    try:
        return datetime.datetime.fromtimestamp(float(value), tz=datetime.timezone.utc)
    except Exception:
        return None


def format_event_timestamp(ts: datetime.datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_timeline_preview(*candidates: str) -> str:
    cleaned = [normalize_whitespace(c) for c in candidates if c]
    if not cleaned:
        return ""
    preview = choose_best_text_preview(cleaned)
    if len(preview) > TIMELINE_PREVIEW_MAX_CHARS:
        preview = preview[:TIMELINE_PREVIEW_MAX_CHARS].rstrip() + "..."
    return preview


def build_select_expr(alias: str, column: str, available: set[str]) -> str:
    if column in available:
        return f"{alias}.{column} AS {column}"
    return f"NULL AS {column}"


def build_keyword_where(alias: str, columns: list[str], keyword: Optional[str]) -> tuple[str, list[str]]:
    keywords = split_keywords(keyword)
    if not keywords or not columns:
        return "", []
    clauses: list[str] = []
    params: list[str] = []
    escape_char = "!"
    for kw in keywords:
        escaped = escape_like(kw, escape_char)
        for col in columns:
            clauses.append(f"{alias}.{col} LIKE ? ESCAPE '{escape_char}'")
            params.append(f"%{escaped}%")
    if not clauses:
        return "", []
    return "(" + " OR ".join(clauses) + ")", params


def make_timeline_event(
    ts: Optional[datetime.datetime],
    event_type: TimelineEventType,
    source: TimelineSource,
    note_id: str,
    note_title: str,
    preview: str,
    source_detail: str,
    confidence: float,
) -> Optional[TimelineEvent]:
    if not ts:
        return None
    return TimelineEvent(
        timestamp=ts,
        event_type=event_type,
        source=source,
        note_id=note_id,
        note_title=note_title,
        content_preview=preview,
        source_detail=source_detail,
        confidence=confidence,
    )


def extract_db_events_icloud(
    conn: sqlite3.Connection,
    keyword: Optional[str],
    max_notes: int,
) -> list[TimelineEvent]:
    profile = build_query_profile(conn, ICLOUD_PROFILE_SPEC)
    obj_cols = profile.available_columns.get("ZICCLOUDSYNCINGOBJECT", set())
    select_cols = [
        build_select_expr("o", "Z_PK", obj_cols),
        build_select_expr("o", "ZIDENTIFIER", obj_cols),
        build_select_expr("o", "ZTITLE1", obj_cols),
        build_select_expr("o", "ZSNIPPET", obj_cols),
        build_select_expr("o", "ZCREATIONDATE", obj_cols),
        build_select_expr("o", "ZMODIFICATIONDATE", obj_cols),
        build_select_expr("o", "ZDELETEDDATE", obj_cols),
        build_select_expr("o", "ZMARKEDFORDELETION", obj_cols),
        build_select_expr("o", "ZLASTOPENEDDATE", obj_cols),
        build_select_expr("o", "ZLASTVIEWEDMODIFICATIONDATE", obj_cols),
    ]
    like_columns = [col for col in ("ZTITLE1", "ZSNIPPET") if col in obj_cols]
    where_clause, params = build_keyword_where("o", like_columns, keyword)
    order_col = "o.Z_PK"
    if "ZMODIFICATIONDATE" in obj_cols:
        order_col = "o.ZMODIFICATIONDATE"
    elif "ZCREATIONDATE" in obj_cols:
        order_col = "o.ZCREATIONDATE"
    sql = f"SELECT {', '.join(select_cols)} FROM ZICCLOUDSYNCINGOBJECT o"
    if where_clause:
        sql += f" WHERE {where_clause}"
    sql += f" ORDER BY {order_col} DESC LIMIT ?"
    params.append(str(max_notes))
    rows = conn.execute(sql, params).fetchall()
    events: list[TimelineEvent] = []
    keywords = split_keywords(keyword)
    for row in rows:
        note_id = row["ZIDENTIFIER"] or f"Z_PK:{row['Z_PK']}"
        title = row["ZTITLE1"] or ""
        snippet = row["ZSNIPPET"] or ""
        preview = build_timeline_preview(snippet, title)
        if keywords and not keyword_matches_any(f"{title} {snippet}", keywords):
            continue
        created = mac_absolute_to_datetime(row["ZCREATIONDATE"])
        modified = mac_absolute_to_datetime(row["ZMODIFICATIONDATE"])
        deleted = mac_absolute_to_datetime(row["ZDELETEDDATE"])
        opened = mac_absolute_to_datetime(row["ZLASTOPENEDDATE"])
        viewed = mac_absolute_to_datetime(row["ZLASTVIEWEDMODIFICATIONDATE"])
        for ts, etype in (
            (created, TimelineEventType.CREATED),
            (modified, TimelineEventType.MODIFIED),
            (deleted, TimelineEventType.DELETED),
            (opened, TimelineEventType.OPENED),
            (viewed, TimelineEventType.VIEWED),
        ):
            event = make_timeline_event(
                ts,
                etype,
                TimelineSource.DB,
                note_id,
                title,
                preview,
                "ZICCLOUDSYNCINGOBJECT",
                TIMELINE_DB_CONFIDENCE,
            )
            if event:
                events.append(event)
        marked_deleted = row["ZMARKEDFORDELETION"]
        if marked_deleted and not deleted:
            event = make_timeline_event(
                modified or created,
                TimelineEventType.MARKED_DELETED,
                TimelineSource.DB,
                note_id,
                title,
                preview,
                "ZMARKEDFORDELETION",
                TIMELINE_DB_CONFIDENCE,
            )
            if event:
                events.append(event)
    return events


def extract_db_events_legacy(
    conn: sqlite3.Connection,
    keyword: Optional[str],
    max_notes: int,
) -> list[TimelineEvent]:
    profile = build_query_profile(conn, LEGACY_PROFILE_SPEC)
    note_cols = profile.available_columns.get("ZNOTE", set())
    body_cols = profile.available_columns.get("ZNOTEBODY", set())
    select_cols = [
        build_select_expr("n", "Z_PK", note_cols),
        build_select_expr("n", "ZTITLE", note_cols),
        build_select_expr("n", "ZDATEEDITED", note_cols),
        build_select_expr("n", "ZCREATIONDATE", note_cols),
        build_select_expr("n", "ZMODIFICATIONDATE", note_cols),
    ]
    if "ZHTMLSTRING" in body_cols:
        select_cols.append(build_select_expr("b", "ZHTMLSTRING", body_cols))
    like_columns = [col for col in ("ZTITLE",) if col in note_cols]
    where_clause, params = build_keyword_where("n", like_columns, keyword)
    order_col = "n.Z_PK"
    if "ZDATEEDITED" in note_cols:
        order_col = "n.ZDATEEDITED"
    elif "ZMODIFICATIONDATE" in note_cols:
        order_col = "n.ZMODIFICATIONDATE"
    elif "ZCREATIONDATE" in note_cols:
        order_col = "n.ZCREATIONDATE"
    sql = f"SELECT {', '.join(select_cols)} FROM ZNOTE n"
    if "ZHTMLSTRING" in body_cols:
        sql += " LEFT JOIN ZNOTEBODY b ON b.ZNOTE = n.Z_PK"
    if where_clause:
        sql += f" WHERE {where_clause}"
    sql += f" ORDER BY {order_col} DESC LIMIT ?"
    params.append(str(max_notes))
    rows = conn.execute(sql, params).fetchall()
    events: list[TimelineEvent] = []
    keywords = split_keywords(keyword)
    for row in rows:
        note_id = f"ZNOTE:{row['Z_PK']}"
        title = row["ZTITLE"] or ""
        body_text = html_to_text(row["ZHTMLSTRING"]) if "ZHTMLSTRING" in row.keys() else ""
        preview = build_timeline_preview(body_text, title)
        if keywords and not keyword_matches_any(f"{title} {body_text}", keywords):
            continue
        created = mac_absolute_to_datetime(row["ZCREATIONDATE"])
        edited = mac_absolute_to_datetime(row["ZDATEEDITED"])
        modified = mac_absolute_to_datetime(row["ZMODIFICATIONDATE"])
        for ts, etype in (
            (created, TimelineEventType.CREATED),
            (edited or modified, TimelineEventType.MODIFIED),
        ):
            event = make_timeline_event(
                ts,
                etype,
                TimelineSource.DB,
                note_id,
                title,
                preview,
                "ZNOTE",
                TIMELINE_DB_CONFIDENCE,
            )
            if event:
                events.append(event)
    return events


def extract_db_events(db_path: Path, keyword: Optional[str], max_notes: int) -> list[TimelineEvent]:
    conn = open_sqlite_readonly(db_path)
    conn.row_factory = sqlite3.Row
    schema = detect_schema(conn)
    try:
        if schema == SchemaType.ICLOUD:
            return extract_db_events_icloud(conn, keyword, max_notes)
        if schema == SchemaType.LEGACY:
            return extract_db_events_legacy(conn, keyword, max_notes)
        events = extract_db_events_icloud(conn, keyword, max_notes)
        if events:
            return events
        return extract_db_events_legacy(conn, keyword, max_notes)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def collect_wal_files(root_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    db_dir = case_dir(root_dir, CASE_DIR_DB_BACKUP)
    for name in (CASE_FILE_NOTESTORE_WAL, CASE_FILE_NOTESTORE_SHM):
        path = db_dir / name
        if path.exists():
            candidates.append(path)
    isolation_dir = case_dir(db_dir, CASE_DIR_WAL_ISOLATION)
    if isolation_dir.exists():
        candidates.extend(sorted(isolation_dir.glob("*.sqlite-wal")))
        candidates.extend(sorted(isolation_dir.glob("*.sqlite-shm")))
    return [p for p in candidates if p.exists() and not p.is_symlink()]


def extract_wal_events(wal_files: list[Path]) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for path in wal_files:
        try:
            stat = path.stat()
        except Exception:
            continue
        for ts, etype in (
            (unix_to_datetime(stat.st_mtime), TimelineEventType.WAL_MTIME),
            (unix_to_datetime(stat.st_ctime), TimelineEventType.WAL_CTIME),
        ):
            event = make_timeline_event(
                ts,
                etype,
                TimelineSource.WAL,
                "",
                "",
                "",
                str(path),
                TIMELINE_WAL_CONFIDENCE,
            )
            if event:
                events.append(event)
    return events


def is_spotlight_signal_file(path: Path) -> bool:
    name = path.name.lower()
    if name in {"store.db", ".store.db", "indexstate"}:
        return True
    if name.endswith(".store.db"):
        return True
    if name.startswith("journalattr"):
        return True
    if name.endswith(".index"):
        return True
    return False


def extract_spotlight_events(spotlight_dir: Path, max_files: int) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    if not spotlight_dir.exists():
        return events
    candidates: list[tuple[float, Path]] = []
    for path in iter_files_safe(spotlight_dir):
        if not is_spotlight_signal_file(path):
            continue
        try:
            stat = path.stat()
        except Exception:
            continue
        candidates.append((stat.st_mtime, path))
    candidates.sort(key=lambda item: item[0], reverse=True)
    for _mtime, path in candidates[:max_files]:
        try:
            stat = path.stat()
        except Exception:
            continue
        for ts, etype in (
            (unix_to_datetime(stat.st_mtime), TimelineEventType.SPOTLIGHT_MTIME),
            (unix_to_datetime(stat.st_ctime), TimelineEventType.SPOTLIGHT_CTIME),
        ):
            event = make_timeline_event(
                ts,
                etype,
                TimelineSource.SPOTLIGHT,
                "",
                "",
                "",
                str(path),
                TIMELINE_SPOTLIGHT_CONFIDENCE,
            )
            if event:
                events.append(event)
    return events


def extract_fs_events(paths: list[Path]) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for path in paths:
        if not path.exists() or path.is_symlink():
            continue
        try:
            stat = path.stat()
        except Exception:
            continue
        for ts, etype in (
            (unix_to_datetime(stat.st_mtime), TimelineEventType.FS_MTIME),
            (unix_to_datetime(stat.st_ctime), TimelineEventType.FS_CTIME),
        ):
            event = make_timeline_event(
                ts,
                etype,
                TimelineSource.FS,
                "",
                "",
                "",
                str(path),
                TIMELINE_FS_CONFIDENCE,
            )
            if event:
                events.append(event)
    return events


def annotate_timeline_anomalies(events: list[TimelineEvent]) -> None:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    future_cutoff = now + datetime.timedelta(seconds=TIMELINE_FUTURE_DRIFT_SECONDS)
    for event in events:
        if event.timestamp.year < TIMELINE_MIN_YEAR:
            event.anomaly = True
            event.anomaly_reason = "timestamp_before_epoch"
        if event.timestamp > future_cutoff:
            event.anomaly = True
            event.anomaly_reason = "timestamp_in_future"

    grouped: dict[str, list[TimelineEvent]] = {}
    for event in events:
        if not event.note_id:
            continue
        grouped.setdefault(event.note_id, []).append(event)
    for note_id, note_events in grouped.items():
        note_events.sort(key=lambda e: e.timestamp)
        created_time: Optional[datetime.datetime] = None
        for idx, event in enumerate(note_events):
            if idx > 0 and event.timestamp < note_events[idx - 1].timestamp:
                event.anomaly = True
                reason = "time_reversal"
                event.anomaly_reason = reason if not event.anomaly_reason else f"{event.anomaly_reason};{reason}"
            if event.event_type == TimelineEventType.CREATED and created_time is None:
                created_time = event.timestamp
        if created_time:
            for event in note_events:
                if event.timestamp < created_time:
                    event.anomaly = True
                    reason = "event_before_created"
                    event.anomaly_reason = reason if not event.anomaly_reason else f"{event.anomaly_reason};{reason}"


def group_events_by_note(events: list[TimelineEvent]) -> dict[str, list[TimelineEvent]]:
    grouped: dict[str, list[TimelineEvent]] = {}
    for event in events:
        if not event.note_id:
            continue
        grouped.setdefault(event.note_id, []).append(event)
    for note_id, note_events in grouped.items():
        note_events.sort(key=lambda e: e.timestamp)
        grouped[note_id] = note_events
    return grouped


def timeline_event_to_dict(event: TimelineEvent, index: int) -> dict[str, Any]:
    return {
        "event_index": index,
        "timestamp": format_event_timestamp(event.timestamp),
        "timestamp_unix": event.timestamp.timestamp(),
        "event_type": event.event_type.value,
        "source": event.source.value,
        "note_id": event.note_id,
        "note_title": event.note_title,
        "content_preview": event.content_preview,
        "source_detail": event.source_detail,
        "confidence": event.confidence,
        "anomaly": event.anomaly,
        "anomaly_reason": event.anomaly_reason,
    }


def write_timeline_csv(out_path: Path, events: list[TimelineEvent]) -> None:
    ensure_dir(out_path.parent)
    try:
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "timestamp_unix",
                    "event_type",
                    "source",
                    "note_id",
                    "note_title",
                    "content_preview",
                    "source_detail",
                    "confidence",
                    "anomaly",
                    "anomaly_reason",
                ]
            )
            for event in events:
                writer.writerow(
                    [
                        format_event_timestamp(event.timestamp),
                        f"{event.timestamp.timestamp():.3f}",
                        event.event_type.value,
                        event.source.value,
                        event.note_id,
                        event.note_title,
                        event.content_preview,
                        event.source_detail,
                        f"{event.confidence:.2f}",
                        event.anomaly,
                        event.anomaly_reason,
                    ]
                )
    except Exception as exc:
        raise RuntimeError(f"Failed to write timeline CSV: {out_path} -> {exc}")


def write_timeline_json(
    out_path: Path,
    events: list[TimelineEvent],
    grouped: dict[str, list[TimelineEvent]],
    spotlight_meta: Optional[dict[str, Any]],
) -> None:
    ensure_dir(out_path.parent)
    payload: dict[str, Any] = {
        "strategy_version": TIMELINE_STRATEGY_VERSION,
        "total_events": len(events),
        "events": [timeline_event_to_dict(event, idx + 1) for idx, event in enumerate(events)],
        "notes": {
            note_id: [timeline_event_to_dict(event, idx + 1) for idx, event in enumerate(items)]
            for note_id, items in grouped.items()
        },
    }
    if spotlight_meta:
        payload["spotlight_meta"] = spotlight_meta
    try:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to write timeline JSON: {out_path} -> {exc}")


def write_timeline_summary(
    out_path: Path,
    events: list[TimelineEvent],
    grouped: dict[str, list[TimelineEvent]],
    spotlight_meta: Optional[dict[str, Any]],
) -> None:
    by_source: dict[str, int] = {}
    by_type: dict[str, int] = {}
    anomalies = 0
    for event in events:
        by_source[event.source.value] = by_source.get(event.source.value, 0) + 1
        by_type[event.event_type.value] = by_type.get(event.event_type.value, 0) + 1
        if event.anomaly:
            anomalies += 1
    payload: dict[str, Any] = {
        "strategy_version": TIMELINE_STRATEGY_VERSION,
        "total_events": len(events),
        "note_count": len(grouped),
        "anomaly_count": anomalies,
        "by_source": by_source,
        "by_event_type": by_type,
    }
    if spotlight_meta:
        payload["spotlight_meta"] = {
            "strategy_version": spotlight_meta.get("strategy_version", ""),
            "run_ts": spotlight_meta.get("run_ts", ""),
            "files_scanned": spotlight_meta.get("files_scanned", 0),
            "search_terms_top": spotlight_meta.get("search_terms_top", [])[:20],
            "note_access_top": spotlight_meta.get("note_access_top", [])[:20],
            "bundle_ids_top": spotlight_meta.get("bundle_ids_top", [])[:20],
            "file_paths_top": spotlight_meta.get("file_paths_top", [])[:20],
            "urls_top": spotlight_meta.get("urls_top", [])[:20],
        }
    try:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to write timeline summary: {out_path} -> {exc}")


def write_timeline_html(
    out_path: Path,
    events: list[TimelineEvent],
    grouped: dict[str, list[TimelineEvent]],
    keyword: Optional[str],
    plotly_path: Optional[Path],
    spotlight_meta: Optional[dict[str, Any]],
) -> None:
    ensure_dir(out_path.parent)
    html_parts = [
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "<meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        "<title>Notes Timeline</title>",
        "<style>",
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f7f7f8;color:#1f1f1f;margin:0;padding:24px;}",
        "h1{margin:0 0 12px 0;} .meta{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:12px;}",
        ".meta-item{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:10px 12px;}",
        "input{padding:6px 10px;border:1px solid #cbd5e1;border-radius:6px;width:320px;}",
        "table{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;}",
        "th,td{padding:8px 10px;border-bottom:1px solid #e5e7eb;font-size:13px;vertical-align:top;}",
        "th{background:#f1f5f9;text-align:left;position:sticky;top:0;}",
        "tr.anomaly{background:#fff1f2;}",
        ".badge{display:inline-block;padding:2px 6px;border-radius:6px;background:#eef2ff;font-size:12px;}",
        ".btn{display:inline-block;padding:2px 8px;border-radius:6px;background:#0ea5e9;color:#fff;text-decoration:none;font-size:12px;}",
        ".section{margin-top:20px;}",
        "details{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:8px 12px;margin-bottom:8px;}",
        "summary{cursor:pointer;font-weight:600;}",
        "</style>",
        "</head>",
        "<body>",
        "<h1>Notes Timeline</h1>",
        f"<div class=\"meta\"><div class=\"meta-item\">Strategy: {TIMELINE_STRATEGY_VERSION}</div>",
        f"<div class=\"meta-item\">Keyword: {html.escape(keyword or 'not provided')}</div>",
        f"<div class=\"meta-item\">Events: {len(events)}</div>",
        f"<div class=\"meta-item\">Notes: {len(grouped)}</div></div>",
        "<label>Filter (note_id/title/source): <input id=\"filter\" placeholder=\"Type a keyword\"></label>",
        "<div class=\"section\">",
        "<table id=\"events\"><thead><tr>",
        "<th>Time (UTC)</th><th>Type</th><th>Source</th><th>Note ID</th>",
        "<th>Title</th><th>Preview</th><th>Detail</th><th>Open</th><th>Confidence</th><th>Anomaly</th>",
        "</tr></thead><tbody>",
    ]
    def build_source_link(detail: str) -> str:
        if not detail:
            return ""
        candidate = detail.split("::", 1)[0].strip()
        if not candidate:
            return ""
        try:
            path = Path(candidate).expanduser()
        except Exception:
            return ""
        if not path.exists():
            return ""
        try:
            href = html.escape(path.resolve().as_uri())
        except Exception:
            return ""
        return f"<a class=\"btn\" href=\"{href}\">Open</a>"

    def build_note_anchor(note_id: str) -> str:
        if not note_id:
            return ""
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", note_id)
        if len(safe) > 80:
            safe = safe[:80]
        return f"note_{safe}"

    def build_note_open_link(note_events: list[TimelineEvent]) -> str:
        for item in note_events:
            link = build_source_link(item.source_detail)
            if link:
                return link
        return ""

    for event in events:
        row_class = "anomaly" if event.anomaly else ""
        anomaly = event.anomaly_reason if event.anomaly else ""
        link_html = build_source_link(event.source_detail)
        note_anchor = build_note_anchor(event.note_id)
        note_html = html.escape(event.note_id)
        if note_anchor and note_html:
            note_html = f"<a href=\"#{note_anchor}\">{note_html}</a>"
        html_parts.append(
            "<tr class=\"%s\" data-filter=\"%s\">" % (
                row_class,
                html.escape(
                    f"{event.note_id} {event.note_title} {event.source.value} "
                    f"{event.event_type.value} {event.content_preview} {event.source_detail}"
                ),
            )
        )
        html_parts.append(f"<td>{format_event_timestamp(event.timestamp)}</td>")
        html_parts.append(f"<td><span class=\"badge\">{event.event_type.value}</span></td>")
        html_parts.append(f"<td>{event.source.value}</td>")
        html_parts.append(f"<td>{note_html}</td>")
        html_parts.append(f"<td>{html.escape(event.note_title)}</td>")
        html_parts.append(f"<td>{highlight(event.content_preview, keyword)}</td>")
        html_parts.append(f"<td>{html.escape(event.source_detail)}</td>")
        html_parts.append(f"<td>{link_html if link_html else '-'}</td>")
        html_parts.append(f"<td>{event.confidence:.2f}</td>")
        html_parts.append(f"<td>{html.escape(anomaly)}</td>")
        html_parts.append("</tr>")
    html_parts.append("</tbody></table></div>")

    if spotlight_meta:
        html_parts.append("<div class=\"section\"><h2>Spotlight Metadata Summary</h2>")
        html_parts.append("<div class=\"meta\">")
        html_parts.append(f"<div class=\"meta-item\">Spotlight Strategy: {html.escape(str(spotlight_meta.get('strategy_version', '')))}</div>")
        html_parts.append(f"<div class=\"meta-item\">Files Scanned: {html.escape(str(spotlight_meta.get('files_scanned', 0)))}</div>")
        html_parts.append("</div>")

        def render_top_list(title: str, items: list[Any]) -> None:
            html_parts.append(f"<h3>{html.escape(title)}</h3>")
            html_parts.append("<ol>")
            for item in items[:15]:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    value, count = item[0], item[1]
                    html_parts.append(f"<li>{html.escape(str(value))} <em>({html.escape(str(count))})</em></li>")
                else:
                    html_parts.append(f"<li>{html.escape(str(item))}</li>")
            html_parts.append("</ol>")

        render_top_list("Search Term Candidates", spotlight_meta.get("search_terms_top", []))
        render_top_list("Note Access Frequency", spotlight_meta.get("note_access_top", []))
        render_top_list("Related App Bundle IDs", spotlight_meta.get("bundle_ids_top", []))
        render_top_list("Related File Paths", spotlight_meta.get("file_paths_top", []))
        render_top_list("Related URLs", spotlight_meta.get("urls_top", []))
        html_parts.append("</div>")

    if plotly_path:
        html_parts.append(
            f"<div class=\"section\"><p>Plotly chart: {html.escape(str(plotly_path))}</p></div>"
        )

    html_parts.append("<div class=\"section\"><h2>Grouped by Note</h2>")
    max_note_blocks = 200
    for idx, (note_id, note_events) in enumerate(grouped.items()):
        if idx >= max_note_blocks:
            html_parts.append("<p>Note-group rendering was truncated after the first 200 entries.</p>")
            break
        title = note_events[0].note_title if note_events else ""
        anchor_id = build_note_anchor(note_id)
        open_link = build_note_open_link(note_events)
        open_label = f" {open_link}" if open_link else ""
        html_parts.append(
            f"<details id=\"{html.escape(anchor_id)}\"><summary>{html.escape(note_id)} "
            f"({len(note_events)}) {html.escape(title)}{open_label}</summary><ul>"
        )
        for event in note_events:
            html_parts.append(
                "<li>%s | %s | %s</li>"
                % (
                    format_event_timestamp(event.timestamp),
                    html.escape(event.event_type.value),
                    html.escape(event.content_preview),
                )
            )
        html_parts.append("</ul></details>")
    html_parts.append("</div>")

    html_parts.append(
        "<script>"
        "const filter=document.getElementById('filter');"
        "filter.addEventListener('input',()=>{"
        "const q=filter.value.toLowerCase();"
        "document.querySelectorAll('#events tbody tr').forEach(row=>{"
        "const hay=row.getAttribute('data-filter').toLowerCase();"
        "row.style.display=(!q||hay.includes(q))?'':'none';"
        "});"
        "});"
        "</script>"
    )
    html_parts.append("</body></html>")
    try:
        out_path.write_text("\n".join(html_parts), encoding="utf-8")
    except Exception as exc:
        raise RuntimeError(f"Failed to write timeline HTML: {out_path} -> {exc}")


def write_timeline_plotly(out_path: Path, events: list[TimelineEvent]) -> Optional[Path]:
    try:
        import plotly.graph_objects as go
    except Exception:
        return None
    if not events:
        return None
    xs = [format_event_timestamp(event.timestamp) for event in events]
    ys = [
        event.note_id if event.note_id else event.source.value
        for event in events
    ]
    fig = go.Figure(
        data=go.Scatter(
            x=xs,
            y=ys,
            mode="markers",
            marker=dict(size=8),
            text=[
                f"{event.event_type.value} | {event.source_detail}"
                for event in events
            ],
            hoverinfo="text",
        )
    )
    fig.update_layout(
        title="Notes Timeline",
        xaxis_title="Time (UTC)",
        yaxis_title="Note ID / Source",
        height=600,
    )
    try:
        fig.write_html(str(out_path), include_plotlyjs="cdn")
    except Exception:
        return None
    return out_path


def build_timeline(
    root_dir: Path,
    out_dir: Path,
    keyword: Optional[str],
    max_notes: int,
    max_events: int,
    spotlight_max_files: int,
    include_fs: bool,
    enable_plotly: bool,
    run_ts: str,
) -> dict[str, str]:
    ensure_dir(out_dir)
    db_path = case_dir(root_dir, CASE_DIR_DB_BACKUP) / CASE_FILE_NOTESTORE_SQLITE
    recovered_db = case_dir(root_dir, CASE_DIR_RECOVERED_DB) / CASE_FILE_RECOVERED_NOTESTORE_SQLITE
    if not db_path.exists() and recovered_db.exists():
        db_path = recovered_db
    events: list[TimelineEvent] = []
    spotlight_meta: Optional[dict[str, Any]] = None
    spotlight_analysis_dir: Optional[Path] = None
    spotlight_events_path: Optional[Path] = None
    if db_path.exists():
        try:
            events.extend(extract_db_events(db_path, keyword, max_notes))
        except Exception as exc:
            log_warn(f"Timeline DB extraction failed: {exc}")
    else:
        log_warn("NoteStore.sqlite was not found. The timeline will include WAL, Spotlight, and filesystem events only.")

    wal_files = collect_wal_files(root_dir)
    if wal_files:
        events.extend(extract_wal_events(wal_files))
    spotlight_dir = case_dir(root_dir, CASE_DIR_SPOTLIGHT_BACKUP)
    if spotlight_dir.exists():
        events.extend(extract_spotlight_events(spotlight_dir, spotlight_max_files))

    spotlight_analysis_dir = find_latest_spotlight_analysis_dir(root_dir)
    spotlight_meta_path: Optional[Path] = None
    if spotlight_analysis_dir:
        spotlight_meta_path = find_latest_file(spotlight_analysis_dir, "spotlight_metadata_*.json")
        spotlight_events_path = find_latest_file(spotlight_analysis_dir, "spotlight_events_*.csv")
    elif spotlight_dir.exists():
        spotlight_analysis_dir = case_dir(out_dir, CASE_DIR_SPOTLIGHT_ANALYSIS)
        spotlight_outputs = parse_spotlight_deep(
            root_dir,
            spotlight_analysis_dir,
            spotlight_max_files,
            SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT,
            SPOTLIGHT_PARSE_MIN_STRING_LEN,
            SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT,
            SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT,
            run_ts,
        )
        if spotlight_outputs:
            meta_path_str = spotlight_outputs.get("spotlight_metadata", "")
            events_path_str = spotlight_outputs.get("spotlight_events", "")
            spotlight_meta_path = Path(meta_path_str) if meta_path_str else None
            spotlight_events_path = Path(events_path_str) if events_path_str else None

    if spotlight_meta_path and spotlight_meta_path.exists():
        spotlight_meta = load_json_file(spotlight_meta_path)
        if spotlight_meta and spotlight_analysis_dir:
            spotlight_meta["analysis_dir"] = str(spotlight_analysis_dir)
            spotlight_meta["metadata_path"] = str(spotlight_meta_path)

    if spotlight_events_path and spotlight_events_path.exists():
        events.extend(load_spotlight_events_csv(spotlight_events_path))

    if include_fs:
        fs_targets: list[Path] = []
        if db_path.exists():
            fs_targets.append(db_path)
        fs_targets.extend(wal_files)
        events.extend(extract_fs_events(fs_targets))

    annotate_timeline_anomalies(events)
    events.sort(key=lambda e: e.timestamp)
    if max_events > 0 and len(events) > max_events:
        events = events[:max_events]
    grouped = group_events_by_note(events)

    csv_path = ensure_unique_file(out_dir / f"timeline_events_{run_ts}.csv")
    json_path = ensure_unique_file(out_dir / f"timeline_events_{run_ts}.json")
    summary_path = ensure_unique_file(out_dir / f"timeline_summary_{run_ts}.json")
    html_path = ensure_unique_file(out_dir / f"timeline_report_{run_ts}.html")
    plotly_path: Optional[Path] = None
    if enable_plotly:
        plotly_path = write_timeline_plotly(out_dir / f"timeline_plot_{run_ts}.html", events)

    write_timeline_csv(csv_path, events)
    write_timeline_json(json_path, events, grouped, spotlight_meta)
    write_timeline_summary(summary_path, events, grouped, spotlight_meta)
    write_timeline_html(html_path, events, grouped, keyword, plotly_path, spotlight_meta)

    return {
        "timeline_csv": str(csv_path),
        "timeline_json": str(json_path),
        "timeline_summary": str(summary_path),
        "timeline_html": str(html_path),
        "timeline_plotly": str(plotly_path) if plotly_path else "",
        "spotlight_analysis_dir": str(spotlight_analysis_dir) if spotlight_analysis_dir else "",
        "spotlight_events": str(spotlight_events_path) if spotlight_events_path else "",
    }


# =============================================================================
