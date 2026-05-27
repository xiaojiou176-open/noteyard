from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Optional

from notes_recovery.core.binary import decode_carved_payload, extract_strings_from_bytes
from notes_recovery.core.keywords import build_variants_for_keywords, split_keywords
from notes_recovery.io import ensure_dir, require_positive_int
from notes_recovery.logging import eprint, log_warn
from notes_recovery.services.recover import evaluate_text_hits


SQLITE_HEADER = b"SQLite format 3\x00"
SQLITE_HEADER_SIZE = 100


def _parse_page_size(header: bytes) -> int:
    if len(header) < SQLITE_HEADER_SIZE:
        raise RuntimeError("SQLite header is truncated.")
    raw = struct.unpack(">H", header[16:18])[0]
    if raw == 1:
        return 65536
    if raw < 512:
        raise RuntimeError(f"Unexpected SQLite page size: {raw}")
    return raw


def parse_sqlite_header(db_path: Path) -> dict[str, int]:
    try:
        with db_path.open("rb") as f:
            header = f.read(SQLITE_HEADER_SIZE)
    except Exception as exc:
        raise RuntimeError(f"Failed to read SQLite header: {db_path} -> {exc}")
    if len(header) < SQLITE_HEADER_SIZE:
        raise RuntimeError(f"SQLite header is truncated: {db_path}")
    if not header.startswith(SQLITE_HEADER):
        log_warn(f"Non-standard SQLite header: {db_path}")
    page_size = _parse_page_size(header)
    freelist_trunk = struct.unpack(">I", header[32:36])[0]
    freelist_count = struct.unpack(">I", header[36:40])[0]
    return {
        "page_size": page_size,
        "freelist_trunk": freelist_trunk,
        "freelist_count": freelist_count,
    }


def read_page(db_path: Path, page_no: int, page_size: int) -> bytes:
    if page_no <= 0:
        return b""
    offset = (page_no - 1) * page_size
    try:
        with db_path.open("rb") as f:
            f.seek(offset)
            return f.read(page_size)
    except Exception:
        return b""


def collect_freelist_pages(
    db_path: Path,
    page_size: int,
    first_trunk: int,
    max_pages: int,
) -> list[int]:
    if first_trunk <= 0 or max_pages <= 0:
        return []
    pages: list[int] = []
    seen: set[int] = set()
    trunk = first_trunk
    while trunk and trunk not in seen and len(pages) < max_pages:
        seen.add(trunk)
        pages.append(trunk)
        page = read_page(db_path, trunk, page_size)
        if len(page) < 8:
            break
        next_trunk = struct.unpack(">I", page[0:4])[0]
        leaf_count = struct.unpack(">I", page[4:8])[0]
        for idx in range(leaf_count):
            if len(pages) >= max_pages:
                break
            start = 8 + idx * 4
            end = start + 4
            if end > len(page):
                break
            leaf = struct.unpack(">I", page[start:end])[0]
            if leaf <= 0 or leaf in seen:
                continue
            pages.append(leaf)
            seen.add(leaf)
        trunk = next_trunk
    return pages


def freelist_carve(
    db_path: Path,
    out_dir: Path,
    keyword: Optional[str],
    min_text_len: int,
    max_pages: int,
    max_output_mb: int,
    max_chars: int,
    run_ts: str,
) -> Path:
    require_positive_int(min_text_len, "minimum text length")
    require_positive_int(max_pages, "maximum freelist page count")
    require_positive_int(max_output_mb, "output size limit (MB)")
    require_positive_int(max_chars, "maximum string character count")
    ensure_dir(out_dir)

    header = parse_sqlite_header(db_path)
    page_size = header["page_size"]
    freelist_trunk = header["freelist_trunk"]
    freelist_count = header["freelist_count"]
    pages = collect_freelist_pages(db_path, page_size, freelist_trunk, max_pages)

    manifest_path = out_dir / f"freelist_manifest_{run_ts}.jsonl"
    meta_path = out_dir / f"freelist_meta_{run_ts}.json"
    hits = 0
    bytes_written = 0
    seen_hashes: set[str] = set()
    keywords = split_keywords(keyword)
    variants_map = build_variants_for_keywords(keywords) if keywords else {}

    for page_no in pages:
        if bytes_written >= max_output_mb * 1024 * 1024:
            break
        payload = read_page(db_path, page_no, page_size)
        if not payload:
            continue
        text, encoding = decode_carved_payload(payload, max_chars)
        if not text or len(text) < min_text_len:
            ascii_text = extract_strings_from_bytes(payload, 4, max_chars)
            if ascii_text and len(ascii_text) >= min_text_len:
                text = ascii_text
                encoding = "ascii_strings"
        if not text or len(text) < min_text_len:
            continue
        if keywords:
            occ, keyword_hits, _weighted = evaluate_text_hits(text, variants_map, False)
            if occ <= 0:
                if encoding != "ascii_strings":
                    ascii_text = extract_strings_from_bytes(payload, 4, max_chars)
                    if ascii_text and len(ascii_text) >= min_text_len:
                        occ, keyword_hits, _weighted = evaluate_text_hits(ascii_text, variants_map, False)
                        if occ > 0:
                            text = ascii_text
                            encoding = "ascii_strings"
                if occ <= 0:
                    continue
        else:
            keyword_hits = 0
        digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        hits += 1
        out_path = out_dir / f"freelist_{page_no:06d}_{run_ts}.txt"
        try:
            with out_path.open("w", encoding="utf-8") as f:
                f.write(text)
        except Exception as exc:
            eprint(f"Failed to write freelist fragment: {out_path} -> {exc}")
            continue
        bytes_written += out_path.stat().st_size if out_path.exists() else 0
        record = {
            "page_no": page_no,
            "offset": (page_no - 1) * page_size,
            "text_len": len(text),
            "encoding": encoding,
            "sha256": digest,
            "keyword_hits": keyword_hits,
            "output": str(out_path),
        }
        try:
            with manifest_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception as exc:
            eprint(f"Failed to write freelist manifest: {manifest_path} -> {exc}")

    meta = {
        "db_path": str(db_path),
        "page_size": page_size,
        "freelist_trunk": freelist_trunk,
        "freelist_count": freelist_count,
        "pages_scanned": len(pages),
        "hits": hits,
        "max_pages": max_pages,
        "max_output_mb": max_output_mb,
    }
    try:
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=True, indent=2)
    except Exception as exc:
        log_warn(f"Failed to write freelist metadata: {meta_path} -> {exc}")

    return meta_path
