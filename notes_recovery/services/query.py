from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from notes_recovery.config import ICLOUD_PROFILE_SPEC, LEGACY_PROFILE_SPEC, QUERY_STRATEGY_VERSION
from notes_recovery.core.pipeline import build_timestamped_file, ensure_unique_file, timestamp_now
from notes_recovery.core.sqlite_utils import (
    build_query_profile,
    detect_schema,
    escape_like,
    open_sqlite_readonly,
    profile_columns,
    write_schema_diagnostics,
)
from notes_recovery.logging import eprint
from notes_recovery.models import QueryProfile, SchemaType


def write_csv(path: Path, columns: list[str], rows: Iterable[sqlite3.Row]) -> None:
    import csv

    try:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([row[col] for col in columns])
    except Exception as exc:
        raise RuntimeError(f"Failed to write CSV: {path} -> {exc}")


def run_query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> tuple[list[str], list[sqlite3.Row]]:
    try:
        cursor = conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return columns, rows
    except Exception as exc:
        raise RuntimeError(f"Query failed: {exc}")


def build_select_list(alias: str, columns: list[str]) -> str:
    return ", ".join([f"{alias}.{col}" for col in columns])


def query_notes(db_path: Path, keyword: Optional[str], out_dir: Path, run_ts: Optional[str] = None) -> None:
    conn = open_sqlite_readonly(db_path)
    try:
        schema = detect_schema(conn)
        print(f"Detected schema: {schema.value}")

        schema_unknown = schema == SchemaType.UNKNOWN
        if schema_unknown:
            eprint("Unable to identify the Notes schema. A diagnostics file will be written for manual review.")
        if not run_ts:
            run_ts = timestamp_now()
        profiles: list[QueryProfile] = []
        active_profile: Optional[QueryProfile] = None
        if schema == SchemaType.ICLOUD:
            active_profile = build_query_profile(conn, ICLOUD_PROFILE_SPEC)
            profiles = [active_profile]
        elif schema == SchemaType.LEGACY:
            active_profile = build_query_profile(conn, LEGACY_PROFILE_SPEC)
            profiles = [active_profile]
        else:
            profiles = [
                build_query_profile(conn, ICLOUD_PROFILE_SPEC),
                build_query_profile(conn, LEGACY_PROFILE_SPEC),
            ]

        diagnostics_path = write_schema_diagnostics(out_dir, run_ts, schema, profiles)
        print(f"Schema diagnostics written: {diagnostics_path}")
        print(f"Query strategy version: {QUERY_STRATEGY_VERSION}")

        if schema_unknown:
            return

        def csv_out(name: str) -> Path:
            path = out_dir / name
            if run_ts:
                return build_timestamped_file(path, run_ts)
            return ensure_unique_file(path)

        if schema == SchemaType.ICLOUD and active_profile:
            object_cols = profile_columns(
                active_profile,
                "ZICCLOUDSYNCINGOBJECT",
                [
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
                ],
            )
            note_data_cols = profile_columns(active_profile, "ZICNOTEDATA", ["Z_PK", "ZDATA"])
            delete_filters = []
            if "ZMARKEDFORDELETION" in object_cols:
                delete_filters.append("o.ZMARKEDFORDELETION = 1")
            if "ZTRASHEDSTATE" in object_cols:
                delete_filters.append("o.ZTRASHEDSTATE = 1")
            if "ZDELETEDDATE" in object_cols:
                delete_filters.append("o.ZDELETEDDATE IS NOT NULL")
            delete_where = " OR ".join(delete_filters) if delete_filters else ""

            if keyword and "ZTITLE1" in object_cols and "ZSNIPPET" in object_cols:
                escaped = escape_like(keyword)
                like_param = f"%{escaped}%"
                sql = (
                    "SELECT o.Z_PK, o.ZIDENTIFIER, o.ZTITLE1, o.ZSNIPPET "
                    "FROM ZICCLOUDSYNCINGOBJECT o "
                    "WHERE (o.ZTITLE1 LIKE ? ESCAPE '\\' OR o.ZSNIPPET LIKE ? ESCAPE '\\') "
                    "ORDER BY o.Z_PK DESC"
                )
                columns, rows = run_query(conn, sql, (like_param, like_param))
                out_path = csv_out("icloud_snippet_search.csv")
                write_csv(out_path, columns, rows)
                print(f"Wrote snippet search results -> {out_path}")

            if delete_where:
                select_cols = build_select_list("o", object_cols)
                extra_cols = ""
                if "ZDATA" in note_data_cols:
                    extra_cols = ", length(d.ZDATA) AS zdata_len"
                sql = (
                    f"SELECT {select_cols}{extra_cols} "
                    "FROM ZICCLOUDSYNCINGOBJECT o "
                    "LEFT JOIN ZICNOTEDATA d ON d.Z_PK = o.ZNOTEDATA "
                    f"WHERE {delete_where} "
                    "ORDER BY o.Z_PK DESC"
                )
                columns, rows = run_query(conn, sql)
                out_path = csv_out("icloud_marked_for_deletion.csv")
                write_csv(out_path, columns, rows)
                print(f"Wrote marked-for-deletion results -> {out_path}")

            if "ZNOTEDATA" in object_cols and "ZDATA" in note_data_cols:
                sql = (
                    "SELECT d.Z_PK, length(d.ZDATA) AS zdata_len "
                    "FROM ZICNOTEDATA d "
                    "LEFT JOIN ZICCLOUDSYNCINGOBJECT o ON o.ZNOTEDATA = d.Z_PK "
                    "WHERE o.Z_PK IS NULL "
                    "ORDER BY zdata_len DESC LIMIT 500"
                )
                columns, rows = run_query(conn, sql)
                out_path = csv_out("icloud_orphan_zicnotedata.csv")
                write_csv(out_path, columns, rows)
                print(f"Wrote orphan data results -> {out_path}")

            if "ZNOTEDATA" in object_cols and "ZDATA" in note_data_cols and "ZTITLE1" in object_cols:
                select_cols = ["o.ZTITLE1"]
                if "ZMARKEDFORDELETION" in object_cols:
                    select_cols.append("o.ZMARKEDFORDELETION")
                select_cols.append("length(d.ZDATA) AS zdata_len")
                if "ZIDENTIFIER" in object_cols:
                    select_cols.append("o.ZIDENTIFIER")
                sql = (
                    f"SELECT {', '.join(select_cols)} "
                    "FROM ZICCLOUDSYNCINGOBJECT o "
                    "JOIN ZICNOTEDATA d ON d.Z_PK = o.ZNOTEDATA "
                    "WHERE o.ZTITLE1 IS NOT NULL "
                    "ORDER BY zdata_len ASC LIMIT 200"
                )
                columns, rows = run_query(conn, sql)
                out_path = csv_out("icloud_small_zdata.csv")
                write_csv(out_path, columns, rows)
                print(f"Wrote small-data-block results -> {out_path}")

        if schema == SchemaType.LEGACY and active_profile:
            note_cols = profile_columns(
                active_profile,
                "ZNOTE",
                ["Z_PK", "ZTITLE", "ZDATEEDITED", "ZCREATIONDATE", "ZMODIFICATIONDATE"],
            )
            body_cols = profile_columns(active_profile, "ZNOTEBODY", ["Z_PK", "ZNOTE", "ZHTMLSTRING"])
            date_expr = None
            if "ZDATEEDITED" in note_cols:
                date_expr = "datetime(n.ZDATEEDITED + 978307200, 'unixepoch') AS edited_utc"
            elif "ZMODIFICATIONDATE" in note_cols:
                date_expr = "datetime(n.ZMODIFICATIONDATE + 978307200, 'unixepoch') AS edited_utc"
            elif "ZCREATIONDATE" in note_cols:
                date_expr = "datetime(n.ZCREATIONDATE + 978307200, 'unixepoch') AS edited_utc"
            order_col = "n.Z_PK"
            if "ZDATEEDITED" in note_cols:
                order_col = "n.ZDATEEDITED"
            elif "ZMODIFICATIONDATE" in note_cols:
                order_col = "n.ZMODIFICATIONDATE"
            elif "ZCREATIONDATE" in note_cols:
                order_col = "n.ZCREATIONDATE"

            select_cols = ["n.Z_PK AS note_id"]
            if "ZTITLE" in note_cols:
                select_cols.append("n.ZTITLE")
            if date_expr:
                select_cols.append(date_expr)
            if "ZHTMLSTRING" in body_cols:
                select_cols.append("b.ZHTMLSTRING")
            sql = (
                f"SELECT {', '.join(select_cols)} "
                "FROM ZNOTE n "
                "LEFT JOIN ZNOTEBODY b ON b.ZNOTE = n.Z_PK "
                f"ORDER BY {order_col} DESC LIMIT 200"
            )
            columns, rows = run_query(conn, sql)
            out_path = csv_out("legacy_recent_notes.csv")
            write_csv(out_path, columns, rows)
            print(f"Wrote recent notes results -> {out_path}")

            if "ZHTMLSTRING" in body_cols:
                sql = (
                    "SELECT b.Z_PK, b.ZNOTE, length(b.ZHTMLSTRING) AS html_len "
                    "FROM ZNOTEBODY b "
                    "LEFT JOIN ZNOTE n ON n.Z_PK = b.ZNOTE "
                    "WHERE n.Z_PK IS NULL "
                    "ORDER BY html_len DESC"
                )
                columns, rows = run_query(conn, sql)
                out_path = csv_out("legacy_orphan_znotebody.csv")
                write_csv(out_path, columns, rows)
                print(f"Wrote orphan body results -> {out_path}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
