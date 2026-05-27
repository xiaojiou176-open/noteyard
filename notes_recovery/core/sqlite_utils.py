from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from urllib.parse import quote

from notes_recovery.config import QUERY_STRATEGY_VERSION
from notes_recovery.io import ensure_dir
from notes_recovery.core.pipeline import ensure_unique_file
from notes_recovery.models import QueryProfile, QueryProfileSpec, SchemaType


def open_sqlite_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise RuntimeError(f"Database does not exist: {db_path}")
    try:
        uri = f"file:{quote(str(db_path))}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as exc:
        raise RuntimeError(f"Failed to open database in read-only mode: {db_path} -> {exc}")


def list_tables(conn: sqlite3.Connection) -> list[str]:
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]
    except Exception as exc:
        raise RuntimeError(f"Failed to read table list: {exc}")


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row[1] for row in rows}
    except Exception:
        return set()


def table_exists(tables: set[str], name: str) -> bool:
    return name in tables


def table_has_columns(conn: sqlite3.Connection, table: str, columns: set[str]) -> bool:
    existing = table_columns(conn, table)
    return bool(existing) and columns.issubset(existing)


def detect_schema(conn: sqlite3.Connection) -> SchemaType:
    tables = set(list_tables(conn))
    score_icloud = 0
    score_legacy = 0

    if table_exists(tables, "ZICCLOUDSYNCINGOBJECT"):
        score_icloud += 3
    if table_exists(tables, "ZICNOTEDATA"):
        score_icloud += 2
    if table_exists(tables, "ZICCLOUDSYNCINGOBJECT") and table_has_columns(
        conn, "ZICCLOUDSYNCINGOBJECT", {"ZTITLE1", "ZSNIPPET"}
    ):
        score_icloud += 2
    if table_exists(tables, "ZICNOTEDATA") and table_has_columns(
        conn, "ZICNOTEDATA", {"ZDATA"}
    ):
        score_icloud += 2

    if table_exists(tables, "ZNOTE"):
        score_legacy += 3
    if table_exists(tables, "ZNOTEBODY"):
        score_legacy += 2
    if table_exists(tables, "ZNOTE") and table_has_columns(
        conn, "ZNOTE", {"ZTITLE", "ZDATEEDITED"}
    ):
        score_legacy += 2
    if table_exists(tables, "ZNOTEBODY") and table_has_columns(
        conn, "ZNOTEBODY", {"ZHTMLSTRING"}
    ):
        score_legacy += 2

    if score_icloud > score_legacy:
        return SchemaType.ICLOUD
    if score_legacy > score_icloud:
        return SchemaType.LEGACY

    if {"ZICCLOUDSYNCINGOBJECT", "ZICNOTEDATA"}.issubset(tables):
        return SchemaType.ICLOUD
    if {"ZNOTE", "ZNOTEBODY"}.issubset(tables):
        return SchemaType.LEGACY
    return SchemaType.UNKNOWN


def build_query_profile(conn: sqlite3.Connection, spec: QueryProfileSpec) -> QueryProfile:
    available_tables = set(list_tables(conn))
    missing_tables: dict[str, str] = {}
    for table in spec.required_tables:
        if table not in available_tables:
            missing_tables[table] = "required"
    for table in spec.optional_tables:
        if table not in available_tables:
            missing_tables[table] = "optional"

    available_columns: dict[str, set[str]] = {}
    missing_columns: dict[str, list[str]] = {}
    for table, expected_cols in spec.table_columns.items():
        if table not in available_tables:
            continue
        existing = table_columns(conn, table)
        available_columns[table] = existing
        expected_set = set(expected_cols)
        missing = sorted(expected_set - existing)
        if missing:
            missing_columns[table] = missing

    return QueryProfile(
        name=spec.name,
        schema=spec.schema,
        strategy_version=QUERY_STRATEGY_VERSION,
        available_tables=available_tables,
        available_columns=available_columns,
        missing_tables=missing_tables,
        missing_columns=missing_columns,
    )


def profile_columns(profile: QueryProfile, table: str, columns: list[str]) -> list[str]:
    existing = profile.available_columns.get(table, set())
    return [col for col in columns if col in existing]


def write_schema_diagnostics(
    out_dir: Path,
    run_ts: str,
    detected_schema: SchemaType,
    profiles: list[QueryProfile],
) -> Path:
    ensure_dir(out_dir)
    out_path = out_dir / f"schema_diagnostics_{run_ts}.csv"
    out_path = ensure_unique_file(out_path)
    rows: list[tuple[str, str, str, str, str, str]] = []
    for profile in profiles:
        if profile.missing_tables or profile.missing_columns:
            summary = (
                f"strategy_version={profile.strategy_version} "
                f"missing_tables={len(profile.missing_tables)} "
                f"missing_columns={sum(len(v) for v in profile.missing_columns.values())}"
            )
        else:
            summary = f"strategy_version={profile.strategy_version} all_expected_fields_present"
        rows.append((detected_schema.value, profile.name, "", "", "summary", summary))
        for table, reason in profile.missing_tables.items():
            rows.append((detected_schema.value, profile.name, table, "", "missing_table", reason))
        for table, cols in profile.missing_columns.items():
            for col in cols:
                rows.append((detected_schema.value, profile.name, table, col, "missing_column", ""))
    try:
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["detected_schema", "profile", "table", "column", "issue", "details"])
            writer.writerows(rows)
    except Exception as exc:
        raise RuntimeError(f"Failed to write schema diagnostics: {out_path} -> {exc}")
    return out_path


def safe_table_columns(conn: sqlite3.Connection, table: str, columns: list[str]) -> list[str]:
    existing = table_columns(conn, table)
    return [col for col in columns if col in existing]


def escape_like(value: str, escape: str = "\\") -> str:
    if value is None:
        return ""
    if not escape:
        escape = "\\"
    return value.replace(escape, escape * 2).replace("%", escape + "%").replace("_", escape + "_")
