from __future__ import annotations

import csv
import hashlib
import re
import subprocess
from pathlib import Path
from typing import Optional

from notes_recovery.case_contract import (
    CASE_DIR_PLUGINS_OUTPUT,
    CASE_DIR_QUERY_OUTPUT,
    CASE_DIR_RECOVERED_BLOBS,
    case_dir,
)
from notes_recovery.config import (
    FRAGMENT_SOURCE_WEIGHTS,
    PLUGIN_TEXT_EXTENSIONS,
    RECOVER_BINARY_PREVIEW_BYTES,
    RECOVER_BINARY_RAW_SLICE_BYTES,
    RECOVER_BINARY_STRINGS_MAX_CHARS,
    RECOVER_MAX_TEXT_CHARS,
    RECOVER_STITCH_MAX_SCAN,
    RECOVER_STITCH_MIN_NON_URL_CHARS,
    RECOVER_TEXT_FILE_MAX_MB,
    RECOVER_TEXT_FILE_PREVIEW_CHARS,
    RECOVER_TEXT_SCAN_DIRS,
    STITCH_CLUSTER_BUCKET_SIZE,
    STITCH_CLUSTER_JACCARD_THRESHOLD,
    STITCH_CLUSTER_LENGTH_BUCKET,
    STITCH_CLUSTER_MAX_BUCKET,
    STITCH_CLUSTER_SIGNATURE_SIZE,
    TEXT_BUNDLE_TEXT_EXTENSIONS,
)
from notes_recovery.core.keywords import (
    build_variants_for_keywords,
    count_occurrences_variants_in_file,
    count_occurrences_variants,
    choose_best_text_preview,
    split_keywords,
)
from notes_recovery.core.scan import (
    classify_binary_target,
    collect_deep_scan_targets,
    collect_deep_scan_targets_extended,
    collect_prefixed_dirs,
    should_skip_recovery_path,
)
from notes_recovery.core.pipeline import timestamp_now
from notes_recovery.io import (
    ensure_dir,
    iter_files_safe,
    read_text_limited,
    require_non_negative_int,
    require_positive_int,
)
from notes_recovery.logging import eprint
from notes_recovery.models import BinaryHit, FragmentSource, SearchVariant, StitchNode, TextFragment
from notes_recovery.services import recover_outputs as recover_outputs_impl
from notes_recovery.services import recover_sqlite as recover_sqlite_impl
from notes_recovery.utils.text import normalize_loose, normalize_whitespace


def get_sqlite3_path() -> Path:
    return recover_sqlite_impl.get_sqlite3_path()


def sqlite_recover(
    db_path: Path,
    out_dir: Path,
    ignore_freelist: bool,
    lost_and_found: str,
) -> Path:
    return recover_sqlite_impl.sqlite_recover(
        db_path,
        out_dir,
        ignore_freelist,
        lost_and_found,
        sqlite3_path_resolver=get_sqlite3_path,
        subprocess_module=subprocess,
        eprint_fn=eprint,
    )


def sanitize_label(label: str) -> str:
    return recover_sqlite_impl.sanitize_label(label)


def evaluate_text_hits(
    text: str,
    variants_map: dict[str, list[SearchVariant]],
    match_all: bool,
) -> tuple[int, int, float]:
    total_occ = 0
    keyword_hits = 0
    weighted = 0.0
    for kw, kw_variants in variants_map.items():
        occ, weighted_occ = count_occurrences_variants(text, kw_variants)
        if occ > 0:
            keyword_hits += 1
        total_occ += occ
        weighted += weighted_occ
    if match_all and keyword_hits < len(variants_map):
        return 0, keyword_hits, 0.0
    return total_occ, keyword_hits, weighted


def build_fragment(
    text: str,
    source: FragmentSource,
    source_detail: str,
    file_path: Path,
    variants_map: dict[str, list[SearchVariant]],
    match_all: bool,
    truncated: bool,
) -> Optional[TextFragment]:
    if not text:
        return None
    occ, keyword_hits, weighted = evaluate_text_hits(text, variants_map, match_all)
    if occ <= 0:
        return None
    length = len(text)
    weight = FRAGMENT_SOURCE_WEIGHTS.get(source, 1.0)
    score = score_hit(weighted or float(occ), length, weight)
    return TextFragment(
        text=text,
        source=source,
        source_detail=source_detail,
        file=str(file_path),
        occurrences=occ,
        keyword_hits=keyword_hits,
        length=length,
        truncated=truncated,
        stitchable=length > 40,
        score=score,
    )


def collect_fragments_from_blobs(
    root_dir: Path,
    variants_map: dict[str, list[SearchVariant]],
    match_all: bool,
    max_chars: int,
    max_items: int,
) -> list[TextFragment]:
    fragments: list[TextFragment] = []
    for blob_dir in collect_prefixed_dirs(root_dir, CASE_DIR_RECOVERED_BLOBS):
        for path in sorted(blob_dir.glob("*.txt")):
            if len(fragments) >= max_items:
                break
            text, truncated = read_text_limited(path, max_chars)
            frag = build_fragment(
                text,
                FragmentSource.BLOB,
                str(path),
                path,
                variants_map,
                match_all,
                truncated,
            )
            if frag:
                fragments.append(frag)
    return fragments


def collect_fragments_from_plugins(
    root_dir: Path,
    variants_map: dict[str, list[SearchVariant]],
    match_all: bool,
    max_chars: int,
    max_items: int,
) -> list[TextFragment]:
    fragments: list[TextFragment] = []
    plugins_dir = case_dir(root_dir, CASE_DIR_PLUGINS_OUTPUT)
    if not plugins_dir.exists():
        return fragments
    for path in iter_files_safe(plugins_dir):
        if len(fragments) >= max_items:
            break
        if path.is_dir() or path.is_symlink():
            continue
        if path.suffix.lower() not in PLUGIN_TEXT_EXTENSIONS and path.name != "plugin.log":
            continue
        text, truncated = read_text_limited(path, max_chars)
        frag = build_fragment(
            text,
            FragmentSource.PLUGIN,
            str(path),
            path,
            variants_map,
            match_all,
            truncated,
        )
        if frag:
            fragments.append(frag)
    return fragments


def collect_fragments_from_csv(
    root_dir: Path,
    variants_map: dict[str, list[SearchVariant]],
    match_all: bool,
    max_rows: int,
) -> list[TextFragment]:
    fragments: list[TextFragment] = []
    query_dirs = collect_prefixed_dirs(root_dir, CASE_DIR_QUERY_OUTPUT)
    for query_dir in query_dirs:
        for csv_file in sorted(query_dir.glob("*.csv")):
            if should_skip_recovery_path(csv_file):
                continue
            try:
                with csv_file.open("r", encoding="utf-8", errors="ignore", newline="") as f:
                    reader = csv.reader(f)
                    _header = next(reader, None)
                    for idx, row in enumerate(reader, start=1):
                        if len(fragments) >= max_rows:
                            return fragments
                        joined = " ".join(row).strip()
                        if not joined:
                            continue
                        fragment = build_fragment(
                            joined,
                            FragmentSource.CSV,
                            f"{csv_file.name}#L{idx}",
                            csv_file,
                            variants_map,
                            match_all,
                            False,
                        )
                        if fragment:
                            fragment.stitchable = False
                            fragments.append(fragment)
            except Exception:
                continue
    return fragments


def collect_fragments_from_text_files(
    root_dir: Path,
    variants_map: dict[str, list[SearchVariant]],
    match_all: bool,
    max_chars: int,
    max_files: int,
    max_file_mb: int,
) -> list[TextFragment]:
    fragments: list[TextFragment] = []
    variants = [v for vs in variants_map.values() for v in vs]
    max_file_bytes = max_file_mb * 1024 * 1024 if max_file_mb > 0 else 0
    for base_name in RECOVER_TEXT_SCAN_DIRS:
        base = root_dir / base_name
        if not base.exists():
            continue
        for file_path in iter_files_safe(base):
            if len(fragments) >= max_files:
                return fragments
            if should_skip_recovery_path(file_path):
                continue
            if file_path.suffix.lower() not in TEXT_BUNDLE_TEXT_EXTENSIONS:
                continue
            try:
                size = file_path.stat().st_size
            except Exception:
                size = 0
            if max_file_bytes > 0 and size > max_file_bytes:
                continue
            occ, _total_len, _weighted = count_occurrences_variants_in_file(file_path, variants)
            if occ <= 0:
                continue
            try:
                text, truncated = read_text_limited(file_path, max_chars)
                fragment = build_fragment(
                    text,
                    FragmentSource.TEXT,
                    base.name,
                    file_path,
                    variants_map,
                    match_all,
                    truncated,
                )
                if fragment:
                    fragment.stitchable = False
                    fragments.append(fragment)
            except Exception:
                continue
    return fragments


def read_binary_preview(path: Path, offset: int, preview_bytes: int) -> str:
    if preview_bytes <= 0:
        return ""
    try:
        file_size = path.stat().st_size
        half = preview_bytes // 2
        start = max(0, offset - half)
        if start > file_size:
            start = max(0, file_size - preview_bytes)
        with path.open("rb") as f:
            f.seek(start)
            data = f.read(preview_bytes)
        candidates = [
            data.decode("utf-8", errors="ignore"),
            data.decode("utf-16le", errors="ignore"),
            data.decode("utf-16be", errors="ignore"),
        ]
        return normalize_whitespace(choose_best_text_preview(candidates))
    except Exception:
        return ""


def collect_fragments_from_deep(
    root_dir: Path,
    variants_map: dict[str, list[SearchVariant]],
    preview_len: int,
    max_hits_per_file: int,
    max_file_mb: int,
    max_files: int,
    deep_all: bool,
) -> tuple[list[TextFragment], list[BinaryHit]]:
    fragments: list[TextFragment] = []
    hits: list[BinaryHit] = []
    max_file_bytes = max_file_mb * 1024 * 1024 if max_file_mb > 0 else 0
    variants = [v for vs in variants_map.values() for v in vs]
    targets = collect_deep_scan_targets_extended(root_dir) if deep_all else collect_deep_scan_targets(root_dir)
    for target in targets:
        if len(fragments) >= max_files:
            return fragments, hits
        if target.is_symlink():
            continue
        if should_skip_recovery_path(target):
            continue
        try:
            offsets, weights = scan_binary_for_variants_offsets(
                target,
                variants,
                max_hits_per_file,
                max_file_bytes,
            )
            if not offsets:
                continue
            _source, _weight, detail = classify_binary_target(target)
            hits.append(BinaryHit(target, offsets, sum(weights.values()), detail))
            for offset in offsets:
                if len(fragments) >= max_files:
                    break
                preview = read_binary_preview(target, offset, preview_len)
                if not preview:
                    continue
                fragment = build_fragment(
                    preview,
                    FragmentSource.BINARY,
                    f"{detail}@{offset}",
                    target,
                    variants_map,
                    False,
                    True,
                )
                if fragment:
                    fragment.stitchable = False
                    fragments.append(fragment)
        except Exception:
            continue
    return fragments, hits


def dedupe_stitch_candidates(candidates: list[TextFragment]) -> list[TextFragment]:
    ordered = sorted(candidates, key=lambda x: (x.length, x.occurrences), reverse=True)
    kept: list[TextFragment] = []
    kept_keys: list[str] = []
    for frag in ordered:
        frag_norm = normalize_loose(frag.text) or frag.text
        frag_key = normalize_whitespace(frag_norm).casefold()
        if any(frag_key in key for key in kept_keys):
            continue
        kept.append(frag)
        kept_keys.append(frag_key)
    return kept


def strip_urls(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"https?://[^\s\"'>]+", "", text)
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned


def overlap_size(a: str, b: str, min_len: int, max_scan: int) -> int:
    if min_len <= 0:
        min_len = 1
    if not a or not b:
        return 0
    a_tail = a[-max_scan:] if len(a) > max_scan else a
    b_head = b[:max_scan] if len(b) > max_scan else b
    a_tail_lower = a_tail.lower()
    b_head_lower = b_head.lower()
    max_len = min(len(a_tail_lower), len(b_head_lower))
    for size in range(max_len, min_len - 1, -1):
        if a_tail_lower[-size:] == b_head_lower[:size]:
            return size
    return 0


def is_trivial_overlap(overlap_text: str, min_non_url_chars: int) -> bool:
    cleaned = strip_urls(overlap_text)
    return len(cleaned) < min_non_url_chars


def normalize_for_fingerprint(text: str) -> str:
    cleaned = strip_urls(text or "")
    cleaned = normalize_whitespace(cleaned).lower()
    return cleaned


def build_text_signature(text: str) -> list[int]:
    if not text:
        return []
    cleaned = normalize_for_fingerprint(text)
    tokens = re.split(r"[^a-z0-9]+", cleaned)
    tokens = [t for t in tokens if len(t) >= 3]
    if not tokens:
        digest = hashlib.sha1(cleaned.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return [int(digest, 16)]
    unique_tokens = sorted(set(tokens))[:2000]
    hashed = sorted(int(hashlib.sha1(token.encode("utf-8")).hexdigest()[:8], 16) for token in unique_tokens)
    return hashed[:STITCH_CLUSTER_SIGNATURE_SIZE]


def signature_bucket(signature: list[int], text_len: int) -> str:
    if not signature:
        return f"len_{text_len // STITCH_CLUSTER_LENGTH_BUCKET}"
    head = signature[:STITCH_CLUSTER_BUCKET_SIZE]
    bucket = sum(head) % STITCH_CLUSTER_MAX_BUCKET
    len_bucket = text_len // STITCH_CLUSTER_LENGTH_BUCKET
    return f"{bucket}_{len_bucket}"


def jaccard_signature(a: list[int], b: list[int]) -> float:
    if not a or not b:
        return 0.0
    set_a = set(a)
    set_b = set(b)
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / max(1, union)


def cluster_fragments_by_signature(fragments: list[tuple[int, TextFragment]]) -> list[list[tuple[int, TextFragment]]]:
    buckets: dict[str, list[tuple[int, TextFragment]]] = {}
    for frag_id, frag in fragments:
        signature = build_text_signature(frag.text)
        key = signature_bucket(signature, frag.length)
        buckets.setdefault(key, []).append((frag_id, frag))

    clusters: list[list[tuple[int, TextFragment]]] = []
    for bucket_items in buckets.values():
        for frag_id, frag in bucket_items:
            placed = False
            sig_a = build_text_signature(frag.text)
            for cluster in clusters:
                sig_b = build_text_signature(cluster[0][1].text)
                if jaccard_signature(sig_a, sig_b) >= STITCH_CLUSTER_JACCARD_THRESHOLD:
                    cluster.append((frag_id, frag))
                    placed = True
                    break
            if not placed:
                clusters.append([(frag_id, frag)])
    return clusters


def compute_stitch_confidence(node: StitchNode) -> float:
    length_score = min(1.0, len(node.text) / 4000.0)
    source_score = min(1.0, len(node.sources) / 4.0)
    merge_score = min(1.0, node.merge_count / 10.0)
    overlap_score = min(1.0, node.overlap_total / 800.0)
    return round(0.4 * length_score + 0.2 * source_score + 0.2 * merge_score + 0.2 * overlap_score, 3)


def stitch_fragments(
    fragments: list[TextFragment],
    min_overlap: int,
    max_scan: int,
    min_non_url_chars: int,
    max_rounds: int,
) -> list[StitchNode]:
    clusters = cluster_fragments_by_signature(list(enumerate(fragments)))
    all_nodes: list[StitchNode] = []
    for cluster_id, cluster in enumerate(clusters, start=1):
        nodes = [
            StitchNode(
                frag.text,
                [frag_id],
                {frag.source.value},
                cluster_id,
                0,
                0,
            )
            for frag_id, frag in cluster
        ]
        rounds = 0
        while rounds < max_rounds:
            best = None
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    a = nodes[i]
                    b = nodes[j]
                    overlap_len = overlap_size(a.text, b.text, min_overlap, max_scan)
                    direction = "ab"
                    if overlap_len == 0:
                        overlap_len = overlap_size(b.text, a.text, min_overlap, max_scan)
                        direction = "ba"
                    if overlap_len < min_overlap:
                        continue
                    overlap_text = a.text[-overlap_len:] if direction == "ab" else b.text[-overlap_len:]
                    if overlap_text and is_trivial_overlap(overlap_text, min_non_url_chars):
                        continue
                    size_bias = min(len(a.text), len(b.text)) / 1000.0
                    merge_score = overlap_len * 10.0 + size_bias
                    if not best or merge_score > best["merge_score"]:
                        best = {
                            "i": i,
                            "j": j,
                            "overlap_len": overlap_len,
                            "direction": direction,
                            "merge_score": merge_score,
                        }
            if not best:
                break
            i = best["i"]
            j = best["j"]
            overlap_len = best["overlap_len"]
            direction = best["direction"]
            a = nodes[i]
            b = nodes[j]
            if direction == "ab":
                merged_text = a.text + b.text[overlap_len:]
            else:
                merged_text = b.text + a.text[overlap_len:]
            merged_ids = sorted(set(a.fragment_ids + b.fragment_ids))
            merged_sources = set(a.sources) | set(b.sources)
            new_node = StitchNode(
                merged_text,
                merged_ids,
                merged_sources,
                cluster_id,
                a.merge_count + b.merge_count + 1,
                a.overlap_total + b.overlap_total + overlap_len,
            )
            for idx in sorted([i, j], reverse=True):
                nodes.pop(idx)
            nodes.append(new_node)
            rounds += 1
            if len(nodes) <= 1:
                break
        all_nodes.extend(nodes)
    return all_nodes


def write_text_content_markdown(
    text: str,
    dst: Path,
    title: str,
    meta_lines: list[str],
    truncated: bool,
) -> None:
    recover_outputs_impl.write_text_content_markdown(text, dst, title, meta_lines, truncated)


def write_text_content_html(
    text: str,
    dst: Path,
    title: str,
    meta_lines: list[str],
    truncated: bool,
) -> None:
    recover_outputs_impl.write_text_content_html(text, dst, title, meta_lines, truncated)


def write_text_content_txt(text: str, dst: Path) -> None:
    recover_outputs_impl.write_text_content_txt(text, dst)


def write_fragments_outputs(
    out_dir: Path,
    fragments: list[TextFragment],
    keyword: str,
    run_ts: str,
) -> Path:
    return recover_outputs_impl.write_fragments_outputs(out_dir, fragments, keyword, run_ts)


def write_stitched_outputs(
    out_dir: Path,
    nodes: list[StitchNode],
    keyword: str,
    run_ts: str,
    variants_map: dict[str, list[SearchVariant]],
) -> Path:
    return recover_outputs_impl.write_stitched_outputs(
        out_dir,
        nodes,
        keyword,
        run_ts,
        variants_map,
        score_hit_fn=score_hit,
        compute_stitch_confidence_fn=compute_stitch_confidence,
    )


def collect_sidecar_paths(path: Path) -> list[Path]:
    return recover_outputs_impl.collect_sidecar_paths(path)


def write_binary_hits_outputs(
    out_dir: Path,
    hits: list[BinaryHit],
    keyword: str,
    run_ts: str,
    preview_bytes: int,
    max_chars: int,
    max_copy_mb: int,
    raw_slice_bytes: int,
) -> None:
    recover_outputs_impl.write_binary_hits_outputs(
        out_dir,
        hits,
        keyword,
        run_ts,
        preview_bytes,
        max_chars,
        max_copy_mb,
        raw_slice_bytes,
    )


def score_hit(occurrences: float, length: int, source_weight: float = 1.0) -> float:
    if length <= 0:
        return 0.0
    density = occurrences / max(1.0, length / 1000.0)
    return (occurrences * 10.0 + density) * source_weight


def build_variant_binary_patterns(variant: SearchVariant, min_utf16_len: int) -> list[bytes]:
    patterns: list[bytes] = []
    seen: set[bytes] = set()

    def add_pat(pat: bytes) -> None:
        if not pat:
            return
        if pat in seen:
            return
        seen.add(pat)
        patterns.append(pat)

    try:
        add_pat(variant.text.encode("utf-8", errors="ignore"))
    except Exception:
        pass
    if len(variant.text) >= min_utf16_len:
        for enc in ("utf-16le", "utf-16be"):
            try:
                add_pat(variant.text.encode(enc, errors="ignore"))
            except Exception:
                continue
    return patterns


def scan_binary_for_variants(
    path: Path,
    variants: list[SearchVariant],
    preview_len: int,
    max_hits_per_file: int,
    max_file_bytes: int,
    chunk_size: int = 4 * 1024 * 1024,
) -> tuple[int, float, str]:
    try:
        file_size = path.stat().st_size
    except Exception:
        return 0, 0.0, ""

    if max_file_bytes > 0 and file_size > max_file_bytes:
        return 0, 0.0, ""

    patterns: list[tuple[SearchVariant, bytes]] = []
    for variant in variants:
        for pat in build_variant_binary_patterns(variant, 3):
            patterns.append((variant, pat))
    if not patterns:
        return 0, 0.0, ""

    max_pat_len = max(len(pat) for _, pat in patterns)
    tail = b""
    offset_base = 0
    hit_weights: dict[int, float] = {}
    first_preview = ""

    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                data = tail + chunk
                for variant, pat in patterns:
                    start = 0
                    while True:
                        idx = data.find(pat, start)
                        if idx == -1:
                            break
                        file_offset = offset_base - len(tail) + idx
                        if file_offset not in hit_weights or variant.weight > hit_weights[file_offset]:
                            hit_weights[file_offset] = variant.weight
                            if not first_preview:
                                first_preview = read_binary_preview(path, file_offset, preview_len)
                        start = idx + max(len(pat), 1)
                        if len(hit_weights) >= max_hits_per_file:
                            break
                    if len(hit_weights) >= max_hits_per_file:
                        break
                if len(hit_weights) >= max_hits_per_file:
                    break
                offset_base += len(chunk)
                if max_pat_len > 1:
                    tail = data[-(max_pat_len - 1):]
                else:
                    tail = b""
    except Exception:
        return 0, 0.0, ""

    occurrences = len(hit_weights)
    weighted_occ = sum(hit_weights.values())
    return occurrences, weighted_occ, first_preview


def scan_binary_for_variants_offsets(
    path: Path,
    variants: list[SearchVariant],
    max_hits_per_file: int,
    max_file_bytes: int,
    chunk_size: int = 4 * 1024 * 1024,
) -> tuple[list[int], dict[int, float]]:
    try:
        file_size = path.stat().st_size
    except Exception:
        return [], {}

    if max_file_bytes > 0 and file_size > max_file_bytes:
        return [], {}

    patterns: list[tuple[SearchVariant, bytes]] = []
    for variant in variants:
        for pat in build_variant_binary_patterns(variant, 3):
            patterns.append((variant, pat))
    if not patterns:
        return [], {}

    max_pat_len = max(len(pat) for _, pat in patterns)
    tail = b""
    offset_base = 0
    hit_weights: dict[int, float] = {}
    offsets: list[int] = []

    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                data = tail + chunk
                for variant, pat in patterns:
                    start = 0
                    while True:
                        idx = data.find(pat, start)
                        if idx == -1:
                            break
                        file_offset = offset_base - len(tail) + idx
                        if file_offset not in hit_weights:
                            offsets.append(file_offset)
                            hit_weights[file_offset] = variant.weight
                        else:
                            hit_weights[file_offset] = max(hit_weights[file_offset], variant.weight)
                        start = idx + max(len(pat), 1)
                        if len(offsets) >= max_hits_per_file:
                            break
                    if len(offsets) >= max_hits_per_file:
                        break
                if len(offsets) >= max_hits_per_file:
                    break
                offset_base += len(chunk)
                if max_pat_len > 1:
                    tail = data[-(max_pat_len - 1):]
                else:
                    tail = b""
    except Exception:
        return [], {}

    return offsets, hit_weights


def recover_notes_by_keyword(
    root_dir: Path,
    keyword: str,
    out_dir: Path,
    min_overlap: int,
    max_fragments: int,
    max_stitch_rounds: int,
    include_deep: bool,
    deep_all: bool,
    deep_max_mb: int,
    deep_max_hits_per_file: int,
    match_all: bool,
    binary_copy: bool,
    binary_copy_max_mb: int,
    run_ts: str,
) -> None:
    if not keyword:
        raise RuntimeError("A keyword or URL is required.")
    require_positive_int(min_overlap, "minimum stitch overlap length")
    require_positive_int(max_fragments, "maximum fragment count")
    require_positive_int(max_stitch_rounds, "maximum stitch round count")
    require_non_negative_int(deep_max_mb, "deep-scan per-file size limit (MB)")
    require_positive_int(deep_max_hits_per_file, "deep-scan max hits per file")
    require_non_negative_int(binary_copy_max_mb, "binary copy size limit (MB)")
    if not run_ts:
        run_ts = timestamp_now()
    ensure_dir(out_dir)

    keywords = split_keywords(keyword)
    variants_map = build_variants_for_keywords(keywords)

    fragments: list[TextFragment] = []
    fragments.extend(
        collect_fragments_from_blobs(
            root_dir,
            variants_map,
            match_all,
            RECOVER_MAX_TEXT_CHARS,
            max_fragments * 5,
        )
    )
    fragments.extend(
        collect_fragments_from_plugins(
            root_dir,
            variants_map,
            match_all,
            RECOVER_MAX_TEXT_CHARS,
            max_fragments * 5,
        )
    )
    fragments.extend(
        collect_fragments_from_csv(
            root_dir,
            variants_map,
            match_all,
            max_fragments * 10,
        )
    )
    fragments.extend(
        collect_fragments_from_text_files(
            root_dir,
            variants_map,
            match_all,
            RECOVER_TEXT_FILE_PREVIEW_CHARS,
            max_fragments * 3,
            RECOVER_TEXT_FILE_MAX_MB,
        )
    )
    binary_hits: list[BinaryHit] = []
    if include_deep:
        deep_fragments, deep_hits = collect_fragments_from_deep(
            root_dir,
            variants_map,
            800,
            deep_max_hits_per_file,
            deep_max_mb,
            max_fragments * 2,
            deep_all,
        )
        fragments.extend(deep_fragments)
        binary_hits.extend(deep_hits)

    fragments.sort(key=lambda x: (x.score, x.length), reverse=True)

    fragments_dir = out_dir / "Fragments"
    stitched_dir = out_dir / "Stitched"
    meta_dir = out_dir / "Meta"
    ensure_dir(meta_dir)

    fragments_manifest = write_fragments_outputs(fragments_dir, fragments, keyword, run_ts)

    stitch_candidates = [f for f in fragments if f.stitchable]
    stitch_candidates = dedupe_stitch_candidates(stitch_candidates)
    if len(stitch_candidates) > max_fragments:
        stitch_candidates = sorted(stitch_candidates, key=lambda x: x.score, reverse=True)[:max_fragments]

    stitched_nodes = stitch_fragments(
        stitch_candidates,
        min_overlap,
        RECOVER_STITCH_MAX_SCAN,
        RECOVER_STITCH_MIN_NON_URL_CHARS,
        max_stitch_rounds,
    )
    stitched_manifest = write_stitched_outputs(
        stitched_dir,
        stitched_nodes,
        keyword,
        run_ts,
        variants_map,
    )

    if binary_copy and binary_hits:
        write_binary_hits_outputs(
            out_dir / "Binary_Hits",
            binary_hits,
            keyword,
            run_ts,
            RECOVER_BINARY_PREVIEW_BYTES,
            RECOVER_BINARY_STRINGS_MAX_CHARS,
            binary_copy_max_mb,
            RECOVER_BINARY_RAW_SLICE_BYTES,
        )

    summary_path = meta_dir / f"recovery_summary_{run_ts}.md"
    try:
        with summary_path.open("w", encoding="utf-8") as f:
            f.write("# Keyword / URL Recovery Summary\n\n")
            f.write(f"- Root: {root_dir}\n")
            f.write(f"- Keyword: {keyword}\n")
            f.write(f"- Timestamp: {run_ts}\n")
            f.write(f"- Fragments: {len(fragments)}\n")
            f.write(f"- StitchCandidates: {len(stitch_candidates)}\n")
            f.write(f"- Stitched: {len(stitched_nodes)}\n")
            f.write(f"- BinaryHits: {len(binary_hits)}\n")
            f.write(f"- Fragments Manifest: {fragments_manifest}\n")
            f.write(f"- Stitched Manifest: {stitched_manifest}\n")
            f.write(f"- Fragments HTML Index: {fragments_dir / f'fragments_index_{run_ts}.html'}\n")
            f.write(f"- Stitched HTML Index: {stitched_dir / f'stitched_index_{run_ts}.html'}\n")
            f.write("\n## Source Breakdown\n\n")
            counter: dict[str, int] = {}
            for frag in fragments:
                counter[frag.source.value] = counter.get(frag.source.value, 0) + 1
            for key, value in sorted(counter.items()):
                f.write(f"- {key}: {value}\n")
    except Exception as exc:
        eprint(f"Failed to write recovery summary: {summary_path} -> {exc}")

    print(f"Keyword recovery completed. Output directory: {out_dir}")
    print(f"Fragments manifest: {fragments_manifest}")
    print(f"Stitched manifest: {stitched_manifest}")
