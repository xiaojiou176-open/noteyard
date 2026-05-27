from __future__ import annotations

import difflib
import html
import re
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from notes_recovery.models import SearchVariant
from notes_recovery.utils.bytes import is_printable_char
from notes_recovery.utils.text import extract_urls, normalize_loose, normalize_whitespace


def split_keywords(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    text = raw.replace("，", ",").replace("|", ",")
    items = [item.strip() for item in text.split(",") if item.strip()]
    return [item for item in items if item]


def keyword_matches_any(text: str, keywords: list[str]) -> bool:
    if not text:
        return False
    text_folded = text.casefold()
    for keyword in keywords:
        if keyword.casefold() in text_folded:
            return True
    return False


def count_occurrences(text: str, keyword: str) -> int:
    if not keyword:
        return 0
    text_fold = text.casefold()
    key_fold = keyword.casefold()
    count = 0
    start = 0
    while True:
        idx = text_fold.find(key_fold, start)
        if idx == -1:
            break
        count += 1
        start = idx + max(len(key_fold), 1)
    return count


def count_occurrences_for_keywords(text: str, keywords: list[str]) -> int:
    if not keywords:
        return 0
    total = 0
    for keyword in keywords:
        total += count_occurrences(text, keyword)
    return total


def build_search_variants(keyword: str) -> list[SearchVariant]:
    raw = keyword.strip()
    if not raw:
        return []

    variants: list[SearchVariant] = []
    seen: set[str] = set()

    def add_variant(value: str, weight: float, label: str) -> None:
        value = value.strip()
        if not value:
            return
        if value in seen:
            return
        seen.add(value)
        variants.append(SearchVariant(value, weight, label))

    add_variant(raw, 2.5, "exact")
    add_variant(raw.lower(), 1.8, "lower")
    add_variant(raw.casefold(), 1.7, "casefold")
    add_variant(html.unescape(raw), 2.0, "html")
    add_variant(unquote(raw), 2.0, "url")
    try:
        add_variant(quote(raw, safe=":/?&=%#@!+,;~"), 1.6, "url_quote")
    except Exception:
        pass
    add_variant(normalize_whitespace(raw), 1.5, "space")
    add_variant(raw.replace("…", "..."), 1.2, "ellipsis")
    add_variant(raw.replace("...", "…"), 1.2, "ellipsis")

    loose = normalize_loose(raw)
    if loose and loose != raw:
        add_variant(loose, 0.8, "loose")

    for url in extract_urls(raw):
        add_variant(url, 2.2, "url")
        try:
            add_variant(quote(url, safe=":/?&=%#@!+,;~"), 1.8, "url_quote")
        except Exception:
            pass
        add_variant(url.lower(), 1.6, "url_lower")
        add_variant(unquote(url), 2.0, "url_unquote")
        if url.endswith("/"):
            add_variant(url.rstrip("/"), 1.6, "url_no_trailing")
        url_loose = normalize_loose(url)
        if url_loose and url_loose != url:
            add_variant(url_loose, 0.7, "url_loose")
        try:
            parsed = urlsplit(url)
            if parsed.scheme or parsed.netloc:
                no_query = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
                add_variant(no_query, 1.8, "url_no_query")
                no_fragment = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
                add_variant(no_fragment, 1.7, "url_no_fragment")
                host = parsed.netloc
                if host:
                    add_variant(host, 1.4, "url_host")
                    host_no_www = host[4:] if host.startswith("www.") else ""
                    if host_no_www:
                        add_variant(host_no_www, 1.3, "url_host_no_www")
                    if parsed.path:
                        add_variant(f"{host}{parsed.path}", 1.5, "url_host_path")
                    if parsed.query:
                        add_variant(f"{host}{parsed.path}?{parsed.query}", 1.2, "url_host_query")
                if parsed.scheme:
                    no_scheme = url.replace(f"{parsed.scheme}://", "", 1)
                    add_variant(no_scheme, 1.8, "url_no_scheme")
                    if no_scheme.startswith("www."):
                        add_variant(no_scheme[4:], 1.6, "url_no_scheme_no_www")
        except Exception:
            pass

    tokens = re.split(r"[\s,，;；:：/\\|]+", raw)
    for token in tokens:
        token = token.strip()
        if len(token) >= 2:
            add_variant(token, 1.0, "token")
            add_variant(token.lower(), 0.9, "token_lower")

    return variants


def build_variants_for_keywords(keywords: list[str]) -> dict[str, list[SearchVariant]]:
    variants_map: dict[str, list[SearchVariant]] = {}
    for keyword in keywords:
        variants_map[keyword] = build_search_variants(keyword)
    return variants_map


def fuzzy_ratio(text: str, keyword: str, max_len: int) -> float:
    if not text or not keyword:
        return 0.0
    text_norm = normalize_whitespace(text)[:max_len]
    key_norm = normalize_whitespace(keyword)
    if not text_norm or not key_norm:
        return 0.0
    return difflib.SequenceMatcher(None, key_norm, text_norm).ratio()


def fuzzy_best_ratio(text: str, keywords: list[str], max_len: int) -> float:
    best = 0.0
    for keyword in keywords:
        ratio = fuzzy_ratio(text, keyword, max_len)
        if ratio > best:
            best = ratio
    return best


def score_preview_text(text: str) -> tuple[float, int]:
    if not text:
        return 0.0, 0
    printable = sum(1 for ch in text if is_printable_char(ch))
    ratio = printable / max(1, len(text))
    return ratio, len(text)


def choose_best_text_preview(candidates: list[str]) -> str:
    best = ""
    best_score: tuple[float, int] = (0.0, 0)
    for candidate in candidates:
        cleaned = normalize_whitespace(candidate)
        score = score_preview_text(cleaned)
        if score > best_score:
            best_score = score
            best = cleaned
    return best


def choose_best_text_preview_with_label(candidates: list[tuple[str, str]]) -> tuple[str, str]:
    best = ""
    best_label = ""
    best_score: tuple[float, int] = (0.0, 0)
    for label, candidate in candidates:
        cleaned = normalize_whitespace(candidate)
        score = score_preview_text(cleaned)
        if score > best_score:
            best_score = score
            best = cleaned
            best_label = label
    return best, best_label


def count_occurrences_variants(text: str, variants: list[SearchVariant]) -> tuple[int, float]:
    if not variants:
        return 0, 0.0
    casefold_text = text.casefold()
    loose_text = ""
    total = 0
    weighted = 0.0
    for variant in variants:
        if variant.label == "loose":
            if not loose_text:
                loose_text = normalize_loose(text)
            occ = count_occurrences(loose_text, variant.text)
        else:
            occ = count_occurrences(casefold_text, variant.text.casefold())
        if occ <= 0:
            continue
        total += occ
        weighted += occ * variant.weight
    return total, weighted


def count_occurrences_variants_in_file(
    path: Path,
    variants: list[SearchVariant],
    chunk_size: int = 1024 * 1024,
) -> tuple[int, int, float]:
    if not variants:
        return 0, 0, 0.0
    texts = []
    for variant in variants:
        if variant.label == "loose":
            texts.append(variant.text)
        else:
            texts.append(variant.text.casefold())
    lengths = [len(t) for t in texts]
    tails = ["" for _ in texts]
    total_occ = 0
    weighted = 0.0
    total_len = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                total_len += len(chunk)
                fold_chunk = chunk.casefold()
                loose_chunk = ""
                for idx, variant in enumerate(variants):
                    if lengths[idx] == 0:
                        continue
                    if variant.label == "loose":
                        if not loose_chunk:
                            loose_chunk = normalize_loose(chunk)
                        text = tails[idx] + loose_chunk
                    else:
                        text = tails[idx] + fold_chunk
                    occ = count_occurrences(text, texts[idx])
                    if occ > 0:
                        total_occ += occ
                        weighted += occ * variant.weight
                    if lengths[idx] > 1:
                        tails[idx] = text[-(lengths[idx] - 1):]
                    else:
                        tails[idx] = ""
    except Exception:
        return 0, 0, 0.0
    return total_occ, total_len, weighted


def count_occurrences_in_file(path: Path, keyword: str, chunk_size: int = 1024 * 1024) -> tuple[int, int]:
    keywords = split_keywords(keyword)
    if not keywords:
        return 0, 0
    lowered = [item.casefold() for item in keywords if item]
    lengths = [len(item) for item in lowered]
    if not lowered:
        return 0, 0
    total = 0
    total_len = 0
    tails = ["" for _ in lowered]
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                total_len += len(chunk)
                chunk_lower = chunk.casefold()
                for idx, key_lower in enumerate(lowered):
                    key_len = lengths[idx]
                    if key_len == 0:
                        continue
                    text = tails[idx] + chunk_lower
                    start = 0
                    while True:
                        pos = text.find(key_lower, start)
                        if pos == -1:
                            break
                        total += 1
                        start = pos + key_len
                    tails[idx] = text[-(key_len - 1):] if key_len > 1 else ""
    except Exception:
        return 0, 0
    return total, total_len
