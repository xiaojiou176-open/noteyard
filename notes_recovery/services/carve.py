from __future__ import annotations

import hashlib
import importlib
import json
import zlib
from pathlib import Path
from typing import Iterable, Optional

from notes_recovery.config import (
    CARVE_ALGO_ALL,
    CARVE_ALGO_DEFAULT,
    CARVE_MAX_OUTPUT_MB_DEFAULT,
    GZIP_MAGIC,
    LZ4_MAGIC,
    LZ4_MAGIC_LEGACY,
    LZFSE_MAGIC_BLOCKS,
)
from notes_recovery.core.binary import decode_carved_payload
from notes_recovery.core.keywords import build_variants_for_keywords, split_keywords
from notes_recovery.io import ensure_dir, require_float_range, require_positive_int
from notes_recovery.logging import eprint, log_warn
from notes_recovery.services.recover import evaluate_text_hits
from notes_recovery.utils.bytes import is_printable_char


def normalize_carve_algorithms(raw: Optional[str]) -> list[str]:
    if not raw:
        raw = CARVE_ALGO_DEFAULT
    items = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not items:
        items = CARVE_ALGO_DEFAULT.split(",")
    if "all" in items:
        items = sorted(CARVE_ALGO_ALL)
    unknown = [item for item in items if item not in CARVE_ALGO_ALL]
    if unknown:
        raise RuntimeError(f"Unknown algorithm(s): {', '.join(unknown)}")
    return items


def is_zlib_header_bytes(data: bytes) -> bool:
    if len(data) < 2:
        return False
    cmf = data[0]
    flg = data[1]
    if (cmf & 0x0F) != 8:
        return False
    if (cmf << 8 | flg) % 31 != 0:
        return False
    if flg & 0x20:
        return False
    return True


def find_compressed_offsets(path: Path, chunk_size: int, algorithms: list[str]) -> Iterable[tuple[int, str]]:
    algo_set = set(algorithms)
    magic_map = []
    if "gzip" in algo_set:
        magic_map.append(("gzip", GZIP_MAGIC))
    if "lz4" in algo_set:
        magic_map.append(("lz4", LZ4_MAGIC))
        magic_map.append(("lz4", LZ4_MAGIC_LEGACY))
    if "lzfse" in algo_set:
        for magic in LZFSE_MAGIC_BLOCKS:
            magic_map.append(("lzfse", magic))

    max_magic_len = max((len(magic) for _algo, magic in magic_map), default=2)
    try:
        with path.open("rb") as f:
            offset = 0
            tail = b""
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                data = tail + chunk
                limit = max(0, len(data) - max_magic_len + 1)
                for i in range(limit):
                    if "zlib" in algo_set and is_zlib_header_bytes(data[i:i + 2]):
                        yield offset - len(tail) + i, "zlib"
                    if magic_map:
                        for algo, magic in magic_map:
                            if data[i:i + len(magic)] == magic:
                                yield offset - len(tail) + i, algo
                tail = data[-(max_magic_len - 1):] if max_magic_len > 1 else b""
                offset += len(chunk)
    except Exception as exc:
        raise RuntimeError(f"Failed to scan compressed headers: {exc}")


def load_lz4_module():
    try:
        import lz4.frame as lz4_frame  # type: ignore
        return lz4_frame
    except Exception:
        return None


def load_lzfse_module():
    for name in ("liblzfse", "pyliblzfse"):
        try:
            module = importlib.import_module(name)
            if hasattr(module, "decompress"):
                return module
        except Exception:
            continue
    return None


def try_decompress_window(data: bytes, algo: str) -> Optional[bytes]:
    if algo == "gzip":
        return zlib.decompress(data, wbits=31)
    if algo == "zlib":
        return zlib.decompress(data, wbits=15)
    if algo == "zlib-raw":
        return zlib.decompress(data, wbits=-15)
    if algo == "lz4":
        lz4_frame = load_lz4_module()
        if not lz4_frame:
            return None
        try:
            return lz4_frame.decompress(data)
        except Exception:
            return None
    if algo == "lzfse":
        lzfse_module = load_lzfse_module()
        if not lzfse_module:
            return None
        try:
            return lzfse_module.decompress(data)
        except Exception:
            return None
    return None


def try_decompress_at(
    path: Path,
    offset: int,
    window_size: int,
    algorithms: list[str],
    max_window_size: int,
    max_output_bytes: int,
    warned_missing: set[str],
) -> tuple[Optional[bytes], str]:
    sizes = [window_size]
    while sizes[-1] < max_window_size:
        sizes.append(min(max_window_size, sizes[-1] * 2))
    for size in sizes:
        with path.open("rb") as f:
            f.seek(offset)
            window = f.read(size)
        if not window:
            continue
        for algo in algorithms:
            try:
                data = try_decompress_window(window, algo)
            except Exception:
                continue
            if data is None:
                if algo in {"lz4", "lzfse"} and algo not in warned_missing:
                    warned_missing.add(algo)
                    log_warn(f"Missing {algo} decoding dependency; skipping that algorithm.")
                continue
            if max_output_bytes > 0 and len(data) > max_output_bytes:
                continue
            return data, algo
    return None, ""


def match_keywords_with_variants(text: str, keywords: list[str], max_variants_per_keyword: int = 40) -> bool:
    if not keywords:
        return True
    variants_map = build_variants_for_keywords(keywords)
    text_folded = text.casefold()
    for variants in variants_map.values():
        count = 0
        for variant in variants:
            if not variant.text:
                continue
            key = variant.text.casefold()
            if key and key in text_folded:
                return True
            count += 1
            if count >= max_variants_per_keyword:
                break
    return False


def text_printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for ch in text if is_printable_char(ch) or ch in "\n\r\t")
    return printable / max(1, len(text))


def should_accept_carved_text(text: str, min_text_len: int, min_ratio: float) -> bool:
    if len(text) < min_text_len:
        return False
    ratio = text_printable_ratio(text)
    return ratio >= min_ratio


def is_gzip_header_bytes(data: bytes) -> bool:
    if len(data) < 4:
        return False
    if data[0] != 0x1F or data[1] != 0x8B:
        return False
    if data[2] != 0x08:
        return False
    flags = data[3]
    return flags <= 0x1F


def find_gzip_offsets(path: Path, chunk_size: int) -> Iterable[int]:
    try:
        with path.open("rb") as f:
            offset = 0
            tail = b""
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                data = tail + chunk
                for i in range(0, max(len(data) - 2, 0)):
                    if data[i:i + 3] == GZIP_MAGIC and is_gzip_header_bytes(data[i:i + 4]):
                        yield offset - len(tail) + i
                tail = data[-2:]
                offset += len(chunk)
    except Exception as exc:
        raise RuntimeError(f"Failed to scan gzip headers: {exc}")


def carve_gzip(
    db_path: Path,
    out_dir: Path,
    keyword: Optional[str],
    max_hits: int,
    window_size: int,
    min_text_len: int,
    min_text_ratio: float = 0.55,
    algorithms: Optional[list[str]] = None,
    max_output_mb: int = CARVE_MAX_OUTPUT_MB_DEFAULT,
) -> None:
    require_positive_int(max_hits, "max hit count")
    require_positive_int(window_size, "decompression window size")
    require_positive_int(min_text_len, "minimum text length")
    require_float_range(min_text_ratio, "minimum readable ratio", 0.0, 1.0)
    require_positive_int(max_output_mb, "decompressed output limit (MB)")
    ensure_dir(out_dir)
    manifest_path = out_dir / "manifest.jsonl"

    hits = 0
    seen_hashes: set[str] = set()
    warned_missing: set[str] = set()
    keywords = split_keywords(keyword)
    variants_map = build_variants_for_keywords(keywords) if keywords else {}
    algo_list = normalize_carve_algorithms(",".join(algorithms) if algorithms else None)
    scan_algos = [algo for algo in algo_list if algo != "zlib-raw"]
    for offset, algo_hint in find_compressed_offsets(db_path, chunk_size=4 * 1024 * 1024, algorithms=scan_algos):
        if hits >= max_hits:
            break
        algo_candidates = [algo_hint]
        if algo_hint == "zlib" and "zlib-raw" in algo_list:
            algo_candidates.append("zlib-raw")
        data, algo_used = try_decompress_at(
            db_path,
            offset,
            window_size,
            algo_candidates,
            max_window_size=8 * 1024 * 1024,
            max_output_bytes=max_output_mb * 1024 * 1024,
            warned_missing=warned_missing,
        )
        if not data or not algo_used:
            continue
        text, encoding = decode_carved_payload(data, min(2_000_000, max(min_text_len * 50, 2000)))
        if not text:
            continue
        if not should_accept_carved_text(text, min_text_len, min_text_ratio):
            continue
        if keywords and not match_keywords_with_variants(text, keywords):
            continue
        occ = 0
        keyword_hits = 0
        if variants_map:
            occ, keyword_hits, _weighted = evaluate_text_hits(text, variants_map, False)
            if occ <= 0:
                continue
        digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)

        hits += 1
        out_file = out_dir / f"blob_{hits:04d}_{algo_used}.txt"
        try:
            with out_file.open("w", encoding="utf-8") as f:
                f.write(text)
        except Exception as exc:
            eprint(f"Failed to write carved text: {out_file} -> {exc}")
            continue

        record = {
            "algorithm_hint": algo_hint,
            "algorithm_used": algo_used,
            "offset": offset,
            "output": str(out_file),
            "text_len": len(text),
            "text_ratio": round(text_printable_ratio(text), 4),
            "sha256": digest,
            "encoding": encoding,
            "occurrences": occ,
            "keyword_hits": keyword_hits,
        }
        try:
            with manifest_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception as exc:
            eprint(f"Failed to write carve manifest: {manifest_path} -> {exc}")

    print(f"Carving completed. Hits: {hits}. Output: {out_dir}")
