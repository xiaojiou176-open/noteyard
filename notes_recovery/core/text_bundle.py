from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Optional

from notes_recovery.case_contract import CASE_DIR_TEXT_BUNDLE
from notes_recovery.config import (
    TEXT_BUNDLE_MAX_CSV_ROWS,
    TEXT_BUNDLE_MAX_MANIFEST_ROWS,
    TEXT_BUNDLE_MAX_TEXT_CHARS,
    TEXT_BUNDLE_TEXT_EXTENSIONS,
)
from notes_recovery.core.keywords import keyword_matches_any, split_keywords
from notes_recovery.core.pipeline import build_timestamped_dir
from notes_recovery.io import ensure_dir, is_within, iter_files_safe, read_text_limited, safe_stat_size
from notes_recovery.logging import eprint
from notes_recovery.utils.text import html_to_text


def markdown_escape_cell(text: str, max_len: int = 160) -> str:
    cleaned = text.replace("\r", " ").replace("\n", " ")
    cleaned = cleaned.replace("|", "\\|")
    if len(cleaned) > max_len:
        return cleaned[:max_len] + "..."
    return cleaned


def write_text_markdown(src: Path, dst: Path, title: str, max_chars: int) -> None:
    ensure_dir(dst.parent)
    text, truncated = read_text_limited(src, max_chars)
    with dst.open("w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"- Source: {src}\n")
        if truncated:
            f.write(f"- Note: content truncated to {max_chars} chars\n")
        f.write("\n```text\n")
        f.write(text)
        if text and not text.endswith("\n"):
            f.write("\n")
        f.write("```\n")


def write_csv_markdown(src: Path, dst: Path, keyword: Optional[str], max_rows: int) -> None:
    ensure_dir(dst.parent)
    summary = csv_summary(src, keyword, max_rows)
    header = summary.get("header", [])
    preview = summary.get("preview", [])
    total = summary.get("total", 0)
    matched = summary.get("matched", 0)
    with dst.open("w", encoding="utf-8") as f:
        f.write(f"# CSV Preview: {src.name}\n\n")
        f.write(f"- Source: {src}\n")
        f.write(f"- Rows: {total} | Matched: {matched}\n\n")
        if not header:
            f.write("No header was found, or the CSV could not be read.\n")
            return
        f.write("| " + " | ".join([markdown_escape_cell(h) for h in header]) + " |\n")
        f.write("| " + " | ".join(["---" for _ in header]) + " |\n")
        for row in preview:
            cells = [markdown_escape_cell(str(c)) for c in row]
            if len(cells) < len(header):
                cells.extend([""] * (len(header) - len(cells)))
            f.write("| " + " | ".join(cells[:len(header)]) + " |\n")


def write_manifest_markdown(src: Path, dst: Path, max_rows: int) -> None:
    ensure_dir(dst.parent)
    rows = []
    try:
        with src.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                rows.append(record)
                if len(rows) >= max_rows:
                    break
    except Exception:
        rows = []
    with dst.open("w", encoding="utf-8") as f:
        f.write(f"# Manifest Preview: {src.name}\n\n")
        f.write(f"- Source: {src}\n")
        f.write(f"- Rows: {len(rows)} (preview)\n\n")
        if not rows:
            f.write("No preview rows are available.\n")
            return
        f.write("| output | offset | text_len |\n")
        f.write("| --- | --- | --- |\n")
        for record in rows:
            output = markdown_escape_cell(str(record.get("output", "")), 120)
            offset = str(record.get("offset", ""))
            text_len = str(record.get("text_len", ""))
            f.write(f"| {output} | {offset} | {text_len} |\n")


def csv_summary(path: Path, keyword: Optional[str], max_items: int) -> dict:
    total = 0
    matched = 0
    preview = []
    keywords = split_keywords(keyword)
    try:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            for row in reader:
                total += 1
                joined = " ".join(row)
                if keywords:
                    if keyword_matches_any(joined, keywords):
                        matched += 1
                        if len(preview) < max_items:
                            preview.append(row)
                else:
                    if len(preview) < max_items:
                        preview.append(row)
            return {"header": header, "total": total, "matched": matched, "preview": preview}
    except Exception as exc:
        return {"header": [], "total": 0, "matched": 0, "preview": [], "error": str(exc)}


def flatten_safe_name(name: str) -> str:
    return name.replace(":", "_")


def shorten_name_if_needed(name: str, max_len: int = 240) -> str:
    if len(name) <= max_len:
        return name
    suffix = Path(name).suffix
    base = name[:-len(suffix)] if suffix else name
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    keep = max_len - len(suffix) - len(digest) - 2
    keep = max(keep, 16)
    base = base[:keep]
    return f"{base}__{digest}{suffix}"


def unique_name(name: str, seen: dict[str, int]) -> str:
    if name not in seen:
        seen[name] = 0
        return name
    seen[name] += 1
    suffix = Path(name).suffix
    base = name[:-len(suffix)] if suffix else name
    return f"{base}__dup{seen[name]}{suffix}"


def build_bundle_filename(rel_path: Path, run_ts: str, suffix: str, ext: str, seen: dict[str, int]) -> str:
    base = "__".join(rel_path.parts)
    base = flatten_safe_name(base)
    base = shorten_name_if_needed(base, 200)
    if suffix:
        base = f"{base}__{suffix}"
    name = f"{base}_{run_ts}{ext}"
    return unique_name(name, seen)


def write_text_copy(src: Path, dst: Path) -> None:
    ensure_dir(dst.parent)
    try:
        with src.open("r", encoding="utf-8", errors="ignore") as fin, dst.open("w", encoding="utf-8") as fout:
            shutil.copyfileobj(fin, fout)
    except Exception as exc:
        eprint(f"Failed to copy text: {src} -> {dst} -> {exc}")


def collect_inventory(root_dir: Path, exclude_dirs: list[Path]) -> list[tuple[Path, int]]:
    items: list[tuple[Path, int]] = []
    for path in iter_files_safe(root_dir):
        if any(is_within(path, ex) for ex in exclude_dirs):
            continue
        items.append((path, safe_stat_size(path)))
    return items


def write_inventory_files(bundle_dir: Path, root_dir: Path, items: list[tuple[Path, int]], run_ts: str) -> None:
    total_bytes = sum(size for _path, size in items)
    md_path = bundle_dir / f"inventory_{run_ts}.md"
    txt_path = bundle_dir / f"inventory_{run_ts}.txt"
    try:
        with txt_path.open("w", encoding="utf-8") as f:
            f.write(f"Root: {root_dir}\n")
            f.write(f"Files: {len(items)} | Bytes: {total_bytes}\n\n")
            for path, size in items:
                rel = path.relative_to(root_dir)
                f.write(f"{size}\t{rel}\n")
    except Exception as exc:
        eprint(f"Failed to write inventory TXT: {txt_path} -> {exc}")
    try:
        with md_path.open("w", encoding="utf-8") as f:
            f.write("# File Inventory\n\n")
            f.write(f"- Root: {root_dir}\n")
            f.write(f"- Files: {len(items)} | Bytes: {total_bytes}\n\n")
            f.write("| bytes | relpath |\n")
            f.write("| --- | --- |\n")
            for path, size in items:
                rel = path.relative_to(root_dir)
                f.write(f"| {size} | {markdown_escape_cell(str(rel), 200)} |\n")
    except Exception as exc:
        eprint(f"Failed to write inventory Markdown: {md_path} -> {exc}")


def generate_text_bundle(root_dir: Path, run_ts: str, keyword: Optional[str]) -> Path:
    bundle_dir = build_timestamped_dir(root_dir / CASE_DIR_TEXT_BUNDLE, run_ts)
    ensure_dir(bundle_dir)

    exclude_dirs = [bundle_dir]
    for path in root_dir.glob(f"{CASE_DIR_TEXT_BUNDLE}*"):
        if path.is_dir() and path not in exclude_dirs:
            exclude_dirs.append(path)
    items = collect_inventory(root_dir, exclude_dirs)
    write_inventory_files(bundle_dir, root_dir, items, run_ts)

    seen: dict[str, int] = {}
    md_count = 0
    txt_count = 0
    csv_count = 0
    manifest_count = 0
    html_count = 0
    error_count = 0

    for path, _size in items:
        rel = path.relative_to(root_dir)
        suffix = path.suffix.lower()

        try:
            if suffix == ".csv":
                csv_count += 1
                md_preview = bundle_dir / build_bundle_filename(rel, run_ts, "preview", ".md", seen)
                write_csv_markdown(path, md_preview, keyword, TEXT_BUNDLE_MAX_CSV_ROWS)
                md_count += 1

                md_full = bundle_dir / build_bundle_filename(rel, run_ts, "full", ".md", seen)
                write_text_markdown(path, md_full, f"CSV Full Text: {rel}", TEXT_BUNDLE_MAX_TEXT_CHARS)
                md_count += 1

                txt_copy = bundle_dir / build_bundle_filename(rel, run_ts, "raw", ".txt", seen)
                write_text_copy(path, txt_copy)
                txt_count += 1
                continue

            if suffix == ".jsonl" or path.name.endswith("manifest.jsonl"):
                manifest_count += 1
                md_preview = bundle_dir / build_bundle_filename(rel, run_ts, "preview", ".md", seen)
                write_manifest_markdown(path, md_preview, TEXT_BUNDLE_MAX_MANIFEST_ROWS)
                md_count += 1

                md_full = bundle_dir / build_bundle_filename(rel, run_ts, "full", ".md", seen)
                write_text_markdown(path, md_full, f"Manifest Full Text: {rel}", TEXT_BUNDLE_MAX_TEXT_CHARS)
                md_count += 1

                txt_copy = bundle_dir / build_bundle_filename(rel, run_ts, "raw", ".txt", seen)
                write_text_copy(path, txt_copy)
                txt_count += 1
                continue

            if suffix in {".html", ".htm"}:
                html_count += 1
                md_raw = bundle_dir / build_bundle_filename(rel, run_ts, "html_raw", ".md", seen)
                write_text_markdown(path, md_raw, f"HTML Raw Content: {rel}", TEXT_BUNDLE_MAX_TEXT_CHARS)
                md_count += 1

                text, truncated = read_text_limited(path, TEXT_BUNDLE_MAX_TEXT_CHARS)
                text_only = html_to_text(text)
                md_text = bundle_dir / build_bundle_filename(rel, run_ts, "html_text", ".md", seen)
                ensure_dir(md_text.parent)
                with md_text.open("w", encoding="utf-8") as f:
                    f.write(f"# HTML Text: {rel}\n\n")
                    f.write(f"- Source: {path}\n")
                    if truncated:
                        f.write(f"- Note: content truncated to {TEXT_BUNDLE_MAX_TEXT_CHARS} chars\n")
                    f.write("\n```text\n")
                    f.write(text_only)
                    if text_only and not text_only.endswith("\n"):
                        f.write("\n")
                    f.write("```\n")
                md_count += 1

                txt_copy = bundle_dir / build_bundle_filename(rel, run_ts, "html_text", ".txt", seen)
                ensure_dir(txt_copy.parent)
                with txt_copy.open("w", encoding="utf-8") as f:
                    f.write(text_only)
                txt_count += 1
                continue

            if suffix in TEXT_BUNDLE_TEXT_EXTENSIONS:
                txt_count += 1
                md_path = bundle_dir / build_bundle_filename(rel, run_ts, "text", ".md", seen)
                write_text_markdown(path, md_path, f"Text: {rel}", TEXT_BUNDLE_MAX_TEXT_CHARS)
                md_count += 1
                txt_copy = bundle_dir / build_bundle_filename(rel, run_ts, "raw", ".txt", seen)
                write_text_copy(path, txt_copy)
                txt_count += 1
                continue

            if suffix in {".sqlite", ".db", ".shm", ".wal"}:
                continue
        except Exception as exc:
            error_count += 1
            eprint(f"Failed to generate text bundle output: {path} -> {exc}")
            continue

    summary_path = bundle_dir / f"bundle_summary_{run_ts}.md"
    try:
        with summary_path.open("w", encoding="utf-8") as f:
            f.write("# Text Bundle Summary\n\n")
            f.write(f"- Root: {root_dir}\n")
            f.write(f"- Timestamp: {run_ts}\n")
            f.write(f"- Keyword: {keyword or ''}\n")
            f.write(f"- Files scanned: {len(items)}\n")
            f.write(f"- CSV files: {csv_count}\n")
            f.write(f"- Manifest files: {manifest_count}\n")
            f.write(f"- HTML files: {html_count}\n")
            f.write(f"- Markdown outputs: {md_count}\n")
            f.write(f"- TXT outputs: {txt_count}\n")
            if error_count:
                f.write(f"- Errors: {error_count}\n")
    except Exception as exc:
        eprint(f"Failed to write bundle summary: {summary_path} -> {exc}")

    print(f"Text bundle generated: {bundle_dir}")
    return bundle_dir
