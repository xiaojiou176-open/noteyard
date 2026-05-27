from __future__ import annotations

import csv
import datetime
import json
from pathlib import Path
from typing import Any, Optional

from notes_recovery.io import ensure_dir, require_positive_int
from notes_recovery.logging import log_warn
from notes_recovery.services import spotlight


def parse_fsevents_timestamp(value: Any) -> Optional[datetime.datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        raw = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            raw = float(text)
        except Exception:
            try:
                return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
            except Exception:
                return None
    if raw <= 0:
        return None
    if raw > 1e12:
        raw = raw / 1000.0
    try:
        return datetime.datetime.fromtimestamp(raw, tz=datetime.timezone.utc)
    except Exception:
        return None


def parse_fsevents_csv(path: Path, max_records: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if max_records > 0 and len(records) >= max_records:
                    break
                ts = parse_fsevents_timestamp(row.get("timestamp") or row.get("time") or row.get("ts"))
                path_value = row.get("path") or row.get("file") or ""
                event = row.get("event") or row.get("flags") or ""
                if not path_value:
                    continue
                records.append(
                    {
                        "timestamp": ts,
                        "path": str(path_value),
                        "event": str(event),
                        "raw": row,
                    }
                )
    except Exception as exc:
        log_warn(f"Failed to read FSEvents CSV: {path} -> {exc}")
    return records


def parse_fsevents_json(path: Path, max_records: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()
        if not content:
            return records
        items: list[Any] = []
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            payload = None
        if payload is not None:
            if isinstance(payload, dict):
                if "events" in payload or "records" in payload:
                    items = payload.get("events", payload.get("records", []))
                else:
                    items = [payload]
            elif isinstance(payload, list):
                items = payload
        else:
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except Exception:
                    continue
        for item in items:
            if max_records > 0 and len(records) >= max_records:
                break
            if not isinstance(item, dict):
                continue
            ts = parse_fsevents_timestamp(item.get("timestamp") or item.get("time") or item.get("ts"))
            path_value = item.get("path") or item.get("file") or ""
            event = item.get("event") or item.get("flags") or ""
            if not path_value:
                continue
            records.append(
                {
                    "timestamp": ts,
                    "path": str(path_value),
                    "event": str(event),
                    "raw": item,
                }
            )
    except Exception as exc:
        log_warn(f"Failed to read FSEvents JSON: {path} -> {exc}")
    return records


def load_fsevents_records(path: Path, max_records: int) -> list[dict[str, Any]]:
    if path.suffix.lower() in {".json", ".jsonl"}:
        return parse_fsevents_json(path, max_records)
    return parse_fsevents_csv(path, max_records)


def normalize_match_path(value: str) -> str:
    return value.strip().lower()


def correlate_fsevents_with_spotlight(
    fsevents_path: Path,
    root_dir: Optional[Path],
    spotlight_events_path: Optional[Path],
    out_dir: Path,
    window_seconds: int,
    max_records: int,
    run_ts: str,
) -> dict[str, str]:
    require_positive_int(window_seconds, "time window (seconds)")
    ensure_dir(out_dir)
    records = load_fsevents_records(fsevents_path, max_records)
    spotlight_events: list[dict[str, Any]] = []

    events_path = spotlight_events_path
    if not events_path and root_dir:
        analysis_dir = spotlight.find_latest_spotlight_analysis_dir(root_dir)
        if analysis_dir:
            events_path = spotlight.find_latest_file(analysis_dir, "spotlight_events_*.csv")

    if events_path and events_path.exists():
        try:
            with events_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ts = parse_fsevents_timestamp(row.get("timestamp_utc"))
                    source_path = row.get("source_path") or ""
                    if not source_path:
                        continue
                    spotlight_events.append(
                        {
                            "timestamp": ts,
                            "path": source_path,
                            "note_id": row.get("note_id") or "",
                            "table": row.get("table") or "",
                            "column": row.get("column") or "",
                        }
                    )
        except Exception as exc:
            log_warn(f"Failed to read Spotlight events: {events_path} -> {exc}")

    matches: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    spotlight_index: dict[str, list[dict[str, Any]]] = {}
    for event in spotlight_events:
        key = normalize_match_path(event["path"])
        spotlight_index.setdefault(key, []).append(event)
        spotlight_index.setdefault(Path(key).name, []).append(event)

    for record in records:
        ts = record.get("timestamp")
        path_value = str(record.get("path") or "")
        if not path_value:
            continue
        key = normalize_match_path(path_value)
        candidates = spotlight_index.get(key, []) + spotlight_index.get(Path(key).name, [])
        matched = False
        for cand in candidates:
            if not ts or not cand.get("timestamp"):
                continue
            delta = abs((ts - cand["timestamp"]).total_seconds())
            if delta <= window_seconds:
                matches.append(
                    {
                        "fsevent_time": ts.isoformat(),
                        "fsevent_path": path_value,
                        "fsevent_event": record.get("event", ""),
                        "spotlight_time": cand["timestamp"].isoformat(),
                        "spotlight_path": cand["path"],
                        "note_id": cand.get("note_id", ""),
                        "table": cand.get("table", ""),
                        "column": cand.get("column", ""),
                        "delta_seconds": int(delta),
                    }
                )
                matched = True
        if not matched:
            unmatched.append(
                {
                    "fsevent_time": ts.isoformat() if ts else "",
                    "fsevent_path": path_value,
                    "fsevent_event": record.get("event", ""),
                }
            )

    matched_path = out_dir / f"fsevents_spotlight_matches_{run_ts}.csv"
    unmatched_path = out_dir / f"fsevents_unmatched_{run_ts}.csv"
    summary_path = out_dir / f"fsevents_summary_{run_ts}.json"

    try:
        with matched_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "fsevent_time",
                    "fsevent_path",
                    "fsevent_event",
                    "spotlight_time",
                    "spotlight_path",
                    "note_id",
                    "table",
                    "column",
                    "delta_seconds",
                ],
            )
            writer.writeheader()
            writer.writerows(matches)
    except Exception as exc:
        log_warn(f"Failed to write FSEvents matches: {matched_path} -> {exc}")

    try:
        with unmatched_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["fsevent_time", "fsevent_path", "fsevent_event"],
            )
            writer.writeheader()
            writer.writerows(unmatched)
    except Exception as exc:
        log_warn(f"Failed to write FSEvents unmatched rows: {unmatched_path} -> {exc}")

    try:
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "fsevents_path": str(fsevents_path),
                    "spotlight_events_path": str(events_path) if events_path else "",
                    "records": len(records),
                    "matches": len(matches),
                    "unmatched": len(unmatched),
                    "window_seconds": window_seconds,
                },
                f,
                ensure_ascii=True,
                indent=2,
            )
    except Exception as exc:
        log_warn(f"Failed to write FSEvents summary: {summary_path} -> {exc}")

    return {
        "fsevents_matches": str(matched_path),
        "fsevents_unmatched": str(unmatched_path),
        "fsevents_summary": str(summary_path),
    }
