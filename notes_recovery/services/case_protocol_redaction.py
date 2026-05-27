from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from notes_recovery.core.pipeline import (
    redact_public_safe_payload,
    sanitize_public_safe_string,
)
from notes_recovery.io import read_text_limited
from notes_recovery.utils.text import html_to_text

from .case_protocol_contract import CaseResource, MAX_CSV_ROWS, MAX_JSON_CHARS, MAX_TEXT_CHARS


def latest_file(root_dir: Path, pattern: str) -> Path | None:
    candidates = [path for path in root_dir.rglob(pattern) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def latest_dir(root_dir: Path, prefix: str) -> Path | None:
    candidates = [
        path for path in root_dir.iterdir() if path.is_dir() and path.name.startswith(prefix)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def relpath(base: Path, path: Path | None) -> str:
    if path is None:
        return "(missing)"
    try:
        return str(path.relative_to(base))
    except Exception:
        return str(path)


def load_json_text(path: Path | None, case_root: Path) -> str:
    if path is None or not path.exists():
        return ""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    redacted = redact_public_safe_payload(payload, case_root)
    text = json.dumps(redacted, ensure_ascii=True, indent=2)
    if len(text) <= MAX_JSON_CHARS:
        return text

    def bounded_json(value: Any, *, depth: int = 0) -> Any:
        if depth >= 3:
            if isinstance(value, (dict, list)):
                return "[truncated nested payload]"
            if isinstance(value, str) and len(value) > 160:
                return value[:157] + "..."
            return value
        if isinstance(value, dict):
            bounded: dict[str, Any] = {}
            items = list(value.items())
            for key, child in items[:12]:
                bounded[str(key)] = bounded_json(child, depth=depth + 1)
            if len(items) > 12:
                bounded["__truncated_keys__"] = len(items) - 12
            return bounded
        if isinstance(value, list):
            bounded_items = [bounded_json(child, depth=depth + 1) for child in value[:12]]
            if len(value) > 12:
                bounded_items.append(f"... {len(value) - 12} more item(s) truncated ...")
            return bounded_items
        if isinstance(value, str) and len(value) > 512:
            return value[:509] + "..."
        return value

    bounded_text = json.dumps(bounded_json(redacted), ensure_ascii=True, indent=2)
    if len(bounded_text) <= MAX_JSON_CHARS:
        return bounded_text
    compact_text = json.dumps(bounded_json(redacted), ensure_ascii=True, separators=(",", ":"))
    if len(compact_text) <= MAX_JSON_CHARS:
        return compact_text
    return json.dumps(
        {
            "truncated": True,
            "preview": compact_text[: MAX_JSON_CHARS - 64],
        },
        ensure_ascii=True,
    )


def read_text(path: Path | None, case_root: Path, *, html: bool = False) -> str:
    if path is None or not path.exists():
        return ""
    text, _truncated = read_text_limited(path, MAX_TEXT_CHARS)
    if html:
        text = html_to_text(text)
    return sanitize_public_safe_string(text, case_root)


def read_csv_rows(
    path: Path | None,
    case_root: Path,
    *,
    max_rows: int = MAX_CSV_ROWS,
) -> list[CaseResource]:
    if path is None or not path.exists():
        return []
    rows: list[CaseResource] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader, start=1):
            clean_row = {
                key: sanitize_public_safe_string(str(value), case_root)
                for key, value in row.items()
            }
            artifact = f"Verification hit {idx}"
            content = json.dumps(clean_row, ensure_ascii=True, sort_keys=True)
            rows.append(
                CaseResource(
                    source_id=f"verification_hit_{idx}",
                    artifact=artifact,
                    relpath=relpath(case_root, path),
                    title=artifact,
                    content=content,
                    kind="verification_hit",
                )
            )
            if len(rows) >= max_rows:
                break
    return rows


def build_resource(
    *,
    source_id: str,
    artifact: str,
    path: Path | None,
    root_dir: Path,
    content: str,
    kind: str,
) -> CaseResource | None:
    if not content.strip():
        return None
    return CaseResource(
        source_id=source_id,
        artifact=artifact,
        relpath=relpath(root_dir, path),
        title=artifact,
        content=content,
        kind=kind,
    )


__all__ = [
    "build_resource",
    "latest_dir",
    "latest_file",
    "load_json_text",
    "read_csv_rows",
    "read_text",
    "relpath",
]
