from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

from notes_recovery.case_contract import (
    CASE_DIR_PLUGINS_OUTPUT,
    CASE_DIR_PROTOBUF_OUTPUT,
    CASE_DIR_QUERY_OUTPUT,
    CASE_DIR_RECOVERED_BLOBS,
    CASE_DIR_RECOVERED_DB,
    CASE_DIR_RECOVERED_NOTES,
    CASE_DIR_VERIFICATION,
)
from notes_recovery.config import (
    FTS_INDEX_BATCH_SIZE,
    FTS_INDEX_DB_NAME,
    FTS_INDEX_TEXT_EXTENSIONS,
)
from notes_recovery.core.binary import decode_carved_payload
from notes_recovery.core.keywords import keyword_matches_any, split_keywords
from notes_recovery.core.scan import collect_prefixed_dirs
from notes_recovery.core.sqlite_utils import list_tables, open_sqlite_readonly, safe_table_columns
from notes_recovery.io import ensure_dir, iter_files_safe
from notes_recovery.logging import log_warn
from notes_recovery.utils.text import infer_title_from_text, strip_html_tags


def safe_path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except Exception:
        return 0.0


def read_text_for_fts(path: Path, max_bytes: int, max_chars: int) -> tuple[str, bool, str]:
    try:
        with path.open("rb") as f:
            data = f.read(max_bytes + 1)
    except Exception as exc:
        log_warn(f"Failed to read FTS input: {path} -> {exc}")
        return "", False, ""
    if not data:
        return "", False, ""
    truncated = len(data) > max_bytes
    data = data[:max_bytes]
    text, label = decode_carved_payload(data, max_chars)
    if not text:
        return "", truncated, label
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        text = strip_html_tags(text)
    return text, truncated, label


def ensure_fts5_available(conn: sqlite3.Connection) -> None:
    try:
        row = conn.execute("SELECT sqlite_compileoption_used('ENABLE_FTS5')").fetchone()
        if row and int(row[0]) == 1:
            return
    except Exception:
        pass
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS __fts5_check USING fts5(content)")
        conn.execute("DROP TABLE __fts5_check")
        return
    except Exception as exc:
        raise RuntimeError("The current sqlite3 build does not support FTS5. Use a sqlite3 build with FTS5 enabled.") from exc


def iter_fts_text_files(root_dir: Path, max_file_mb: int) -> Iterable[Path]:
    roots: list[Path] = []
    for prefix in (
        CASE_DIR_RECOVERED_NOTES,
        CASE_DIR_RECOVERED_BLOBS,
        CASE_DIR_QUERY_OUTPUT,
        CASE_DIR_VERIFICATION,
        CASE_DIR_PROTOBUF_OUTPUT,
    ):
        roots.extend(collect_prefixed_dirs(root_dir, prefix))
    seen: set[Path] = set()
    max_bytes = max(1, max_file_mb) * 1024 * 1024
    for base in roots:
        for path in iter_files_safe(base):
            if path in seen:
                continue
            seen.add(path)
            if not path.is_file():
                continue
            if path.suffix.lower() not in FTS_INDEX_TEXT_EXTENSIONS:
                continue
            try:
                if path.stat().st_size > max_bytes:
                    continue
            except Exception:
                continue
            yield path


def resolve_recovered_db_path(root_dir: Path, db_path: Optional[Path]) -> Optional[Path]:
    if db_path:
        return db_path
    candidates: list[Path] = []
    for base in collect_prefixed_dirs(root_dir, CASE_DIR_RECOVERED_DB):
        for path in base.glob("*.sqlite"):
            if path.is_file():
                candidates.append(path)
    if not candidates:
        return None
    return sorted(candidates, key=safe_path_mtime, reverse=True)[0]


def build_fts_index(
    root_dir: Path,
    out_dir: Path,
    keyword: Optional[str],
    source_mode: str,
    db_path: Optional[Path],
    db_table: Optional[str],
    db_columns: list[str],
    db_title_column: Optional[str],
    max_docs: int,
    max_file_mb: int,
    max_text_chars: int,
) -> Path:
    ensure_dir(out_dir)
    fts_db_path = out_dir / FTS_INDEX_DB_NAME
    if fts_db_path.exists():
        fts_db_path.unlink()
    conn = sqlite3.connect(fts_db_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    ensure_fts5_available(conn)
    conn.execute("CREATE TABLE docs_meta (doc_id INTEGER PRIMARY KEY, path TEXT, source TEXT, title TEXT, bytes INTEGER, truncated INTEGER)")
    conn.execute("CREATE VIRTUAL TABLE docs_fts USING fts5(title, content, source, path)")

    doc_id = 0
    total_docs = 0
    batch_count = 0
    skipped = 0
    sources: Counter[str] = Counter()
    keyword_list = split_keywords(keyword)

    def insert_doc(title: str, content: str, source: str, path_str: str, size: int, truncated: bool) -> None:
        nonlocal doc_id, total_docs, batch_count
        if not content:
            return
        doc_id += 1
        conn.execute(
            "INSERT INTO docs_meta(doc_id, path, source, title, bytes, truncated) VALUES (?, ?, ?, ?, ?, ?)",
            (doc_id, path_str, source, title, size, int(truncated)),
        )
        conn.execute(
            "INSERT INTO docs_fts(rowid, title, content, source, path) VALUES (?, ?, ?, ?, ?)",
            (doc_id, title, content, source, path_str),
        )
        total_docs += 1
        sources[source] += 1
        batch_count += 1
        if batch_count >= FTS_INDEX_BATCH_SIZE:
            conn.execute("COMMIT")
            conn.execute("BEGIN")
            batch_count = 0

    try:
        conn.execute("BEGIN")
        if source_mode in {"notes", "all"}:
            for path in iter_fts_text_files(root_dir, max_file_mb):
                if total_docs >= max_docs:
                    break
                text, truncated, _label = read_text_for_fts(path, max_file_mb * 1024 * 1024, max_text_chars)
                if not text:
                    skipped += 1
                    continue
                if keyword_list and not keyword_matches_any(text, keyword_list):
                    continue
                title = infer_title_from_text(path, text)
                insert_doc(title, text, "notes_files", str(path), len(text.encode("utf-8", errors="ignore")), truncated)

        if source_mode in {"db", "all"}:
            resolved_db = resolve_recovered_db_path(root_dir, db_path)
            if resolved_db:
                db_conn = open_sqlite_readonly(resolved_db)
                try:
                    db_sources = []
                    if db_table and db_columns:
                        db_sources.append(("custom", db_table, db_columns, db_title_column))
                    else:
                        tables = set(list_tables(db_conn))
                        if "ZICCLOUDSYNCINGOBJECT" in tables:
                            cols = safe_table_columns(db_conn, "ZICCLOUDSYNCINGOBJECT", ["ZTITLE1", "ZSNIPPET"])
                            if cols:
                                db_sources.append(("icloud", "ZICCLOUDSYNCINGOBJECT", cols, "ZTITLE1"))
                        if {"ZNOTE", "ZNOTEBODY"}.issubset(tables):
                            cols = safe_table_columns(db_conn, "ZNOTEBODY", ["ZHTMLSTRING"])
                            if cols:
                                db_sources.append(("legacy", "ZNOTEBODY", cols, None))

                    for source_label, table, cols, title_col in db_sources:
                        if total_docs >= max_docs:
                            break
                        select_cols = cols[:]
                        if title_col and title_col not in select_cols:
                            select_cols.append(title_col)
                        sql = f"SELECT {', '.join(select_cols)} FROM {table} LIMIT ?"
                        try:
                            rows = db_conn.execute(sql, (max_docs,)).fetchall()
                        except Exception as exc:
                            log_warn(f"Failed to read FTS source table: {table} -> {exc}")
                            continue
                        for row in rows:
                            if total_docs >= max_docs:
                                break
                            values = []
                            for col in cols:
                                val = row[col]
                                if val is None:
                                    continue
                                values.append(str(val))
                            if not values:
                                continue
                            content = "\n".join(values)
                            if keyword_list and not keyword_matches_any(content, keyword_list):
                                continue
                            title = ""
                            if title_col and row[title_col]:
                                title = str(row[title_col])
                            insert_doc(title, content, f"db_{source_label}", f"{resolved_db}:{table}", len(content.encode("utf-8", errors="ignore")), False)
                finally:
                    try:
                        db_conn.close()
                    except Exception:
                        pass
    finally:
        conn.execute("COMMIT")
        conn.close()

    summary_path = out_dir / "fts_summary.md"
    try:
        with summary_path.open("w", encoding="utf-8") as f:
            f.write("# FTS Index Summary\n\n")
            f.write(f"- Root: {root_dir}\n")
            f.write(f"- Docs: {total_docs}\n")
            f.write(f"- Skipped: {skipped}\n")
            f.write("\n## Sources\n\n")
            for key, value in sources.most_common():
                f.write(f"- {key}: {value}\n")
    except Exception as exc:
        log_warn(f"Failed to write FTS summary: {summary_path} -> {exc}")

    return fts_db_path
