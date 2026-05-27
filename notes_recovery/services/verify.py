from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from notes_recovery.case_contract import (
    CASE_DIR_PLUGINS_OUTPUT,
    CASE_DIR_QUERY_OUTPUT,
    CASE_DIR_RECOVERED_BLOBS,
    case_dir,
)
from notes_recovery.core.keywords import (
    build_variants_for_keywords,
    count_occurrences_variants,
    count_occurrences_variants_in_file,
    fuzzy_best_ratio,
    split_keywords,
)
from notes_recovery.core.pipeline import timestamp_now
from notes_recovery.core.scan import (
    classify_binary_target,
    collect_deep_scan_targets,
    collect_deep_scan_targets_extended,
    collect_prefixed_dirs,
    should_skip_recovery_path,
)
from notes_recovery.io import (
    ensure_dir,
    iter_files_safe,
    read_text_limited,
    require_float_range,
    require_non_negative_float,
    require_non_negative_int,
    require_positive_int,
    safe_read_text,
)
from notes_recovery.logging import eprint
from notes_recovery.models import HitSource
from notes_recovery.services.recover import (
    scan_binary_for_variants,
)


def is_plugin_text_candidate(path: Path) -> bool:
    if path.name == "plugin.log":
        return True
    return path.suffix.lower() in {".txt", ".log", ".csv", ".json", ".md", ".html", ".htm", ".xml"}


def score_verify_hit(
    occurrences: float,
    length: int,
    source_weight: float,
    keyword_hits: int,
    total_keywords: int,
    fuzzy_ratio: float,
    fuzzy_boost: float,
) -> tuple[float, float]:
    if length <= 0:
        length = 1
    density = occurrences / max(1.0, length / 1000.0)
    coverage = keyword_hits / max(1, total_keywords)
    base = (occurrences * 10.0 + density) * source_weight
    coverage_boost = 0.7 + 0.3 * coverage
    fuzzy_bonus = fuzzy_ratio * fuzzy_boost * source_weight
    return base * coverage_boost + fuzzy_bonus, coverage


def verify_hits(
    root_dir: Path,
    keyword: str,
    top_n: int,
    preview_len: int,
    out_dir: Path,
    deep: bool = True,
    deep_max_mb: int = 0,
    deep_max_hits_per_file: int = 200,
    match_all: bool = False,
    fuzzy: bool = True,
    fuzzy_threshold: float = 0.72,
    fuzzy_boost: float = 6.0,
    fuzzy_max_len: int = 2000,
    run_ts: Optional[str] = None,
    deep_all: bool = True,
) -> None:
    require_positive_int(top_n, "Top N")
    require_positive_int(preview_len, "preview length")
    require_non_negative_int(deep_max_mb, "deep-scan per-file size limit (MB)")
    require_positive_int(deep_max_hits_per_file, "deep-scan max hits per file")
    require_float_range(fuzzy_threshold, "fuzzy-match threshold", 0.0, 1.0)
    require_non_negative_float(fuzzy_boost, "fuzzy-match weight multiplier")
    require_positive_int(fuzzy_max_len, "fuzzy-match max comparison length")
    if not run_ts:
        run_ts = timestamp_now()
    query_dirs = collect_prefixed_dirs(root_dir, CASE_DIR_QUERY_OUTPUT)
    blob_dirs = collect_prefixed_dirs(root_dir, CASE_DIR_RECOVERED_BLOBS)

    hits = []
    csv_rows_scanned = 0
    csv_hits = 0
    blob_files_scanned = 0
    blob_hits = 0
    plugin_files_scanned = 0
    plugin_hits = 0
    deep_files_scanned = 0
    deep_hits = 0

    keywords = split_keywords(keyword)
    variants_map = build_variants_for_keywords(keywords)
    variants = [v for vs in variants_map.values() for v in vs]
    total_keywords = max(1, len(variants_map))

    for query_dir in query_dirs:
        for csv_file in sorted(query_dir.glob("*.csv")):
            try:
                with csv_file.open("r", encoding="utf-8", errors="ignore", newline="") as f:
                    reader = csv.reader(f)
                    _header = next(reader, None)
                    for idx, row in enumerate(reader, start=1):
                        csv_rows_scanned += 1
                        text = " ".join(row)
                        occ = 0
                        weighted_occ = 0.0
                        keyword_hits = 0
                        for _kw, kw_variants in variants_map.items():
                            kw_occ, kw_weighted = count_occurrences_variants(text, kw_variants)
                            if kw_occ > 0:
                                keyword_hits += 1
                            occ += kw_occ
                            weighted_occ += kw_weighted
                        if match_all and keyword_hits < len(variants_map):
                            continue
                        fuzzy_ratio_value = 0.0
                        if fuzzy:
                            fuzzy_ratio_value = fuzzy_best_ratio(text, keywords, fuzzy_max_len)
                            if occ <= 0 and fuzzy_ratio_value < fuzzy_threshold:
                                continue
                        if occ <= 0:
                            if not fuzzy:
                                continue
                        csv_hits += 1
                        length = len(text)
                        score, coverage = score_verify_hit(
                            weighted_occ,
                            length,
                            1.2,
                            keyword_hits,
                            total_keywords,
                            fuzzy_ratio_value,
                            fuzzy_boost,
                        )
                        preview = text[:preview_len]
                        hits.append({
                            "source": HitSource.CSV.value,
                            "source_detail": CASE_DIR_QUERY_OUTPUT,
                            "file": str(csv_file),
                            "row": idx,
                            "score": score,
                            "occ": occ,
                            "keyword_hits": keyword_hits,
                            "coverage": coverage,
                            "fuzzy_ratio": fuzzy_ratio_value,
                            "length": length,
                            "source_weight": 1.2,
                            "preview": preview,
                        })
            except Exception:
                continue

    for blobs_dir in blob_dirs:
        for blob_file in sorted(blobs_dir.glob("*.txt")):
            blob_files_scanned += 1
            occ = 0
            length = 0
            weighted_occ = 0.0
            keyword_hits = 0
            for _kw, kw_variants in variants_map.items():
                kw_occ, kw_len, kw_weighted = count_occurrences_variants_in_file(blob_file, kw_variants)
                length = max(length, kw_len)
                if kw_occ > 0:
                    keyword_hits += 1
                occ += kw_occ
                weighted_occ += kw_weighted
            if match_all and keyword_hits < len(variants_map):
                continue
            fuzzy_ratio_value = 0.0
            preview = safe_read_text(blob_file, preview_len)
            if fuzzy:
                fuzzy_ratio_value = fuzzy_best_ratio(preview, keywords, fuzzy_max_len)
                if occ <= 0 and fuzzy_ratio_value < fuzzy_threshold:
                    continue
            if occ <= 0:
                if not fuzzy:
                    continue
            blob_hits += 1
            score, coverage = score_verify_hit(
                weighted_occ,
                length,
                1.5,
                keyword_hits,
                total_keywords,
                fuzzy_ratio_value,
                fuzzy_boost,
            )
            hits.append({
                "source": HitSource.BLOB.value,
                "source_detail": CASE_DIR_RECOVERED_BLOBS,
                "file": str(blob_file),
                "row": 0,
                "score": score,
                "occ": occ,
                "keyword_hits": keyword_hits,
                "coverage": coverage,
                "fuzzy_ratio": fuzzy_ratio_value,
                "length": length,
                "source_weight": 1.5,
                "preview": preview,
            })

    plugins_root = case_dir(root_dir, CASE_DIR_PLUGINS_OUTPUT)
    if plugins_root.exists() and plugins_root.is_dir():
        for file_path in iter_files_safe(plugins_root):
            if should_skip_recovery_path(file_path):
                continue
            if not is_plugin_text_candidate(file_path):
                continue
            plugin_files_scanned += 1
            try:
                text, _truncated = read_text_limited(file_path, preview_len)
            except Exception:
                continue
            if not text:
                continue
            occ = 0
            weighted_occ = 0.0
            keyword_hits = 0
            for _kw, kw_variants in variants_map.items():
                kw_occ, kw_weighted = count_occurrences_variants(text, kw_variants)
                if kw_occ > 0:
                    keyword_hits += 1
                occ += kw_occ
                weighted_occ += kw_weighted
            if match_all and keyword_hits < len(variants_map):
                continue
            fuzzy_ratio_value = 0.0
            if fuzzy:
                fuzzy_ratio_value = fuzzy_best_ratio(text, keywords, fuzzy_max_len)
                if occ <= 0 and fuzzy_ratio_value < fuzzy_threshold:
                    continue
            if occ <= 0:
                if not fuzzy:
                    continue
            plugin_hits += 1
            length = len(text)
            try:
                rel = file_path.relative_to(plugins_root)
                source_detail = rel.parts[0] if rel.parts else CASE_DIR_PLUGINS_OUTPUT
            except Exception:
                source_detail = CASE_DIR_PLUGINS_OUTPUT
            score, coverage = score_verify_hit(
                weighted_occ,
                length,
                1.1,
                keyword_hits,
                total_keywords,
                fuzzy_ratio_value,
                fuzzy_boost,
            )
            hits.append({
                "source": HitSource.PLUGIN.value,
                "source_detail": source_detail,
                "file": str(file_path),
                "row": 0,
                "score": score,
                "occ": occ,
                "keyword_hits": keyword_hits,
                "coverage": coverage,
                "fuzzy_ratio": fuzzy_ratio_value,
                "length": length,
                "source_weight": 1.1,
                "preview": text[:preview_len],
            })

    if deep:
        max_file_bytes = deep_max_mb * 1024 * 1024 if deep_max_mb > 0 else 0
        targets = collect_deep_scan_targets_extended(root_dir) if deep_all else collect_deep_scan_targets(root_dir)
        for target in targets:
            if target.is_symlink():
                continue
            if should_skip_recovery_path(target):
                continue
            deep_files_scanned += 1
            try:
                occ, weighted, preview = scan_binary_for_variants(
                    target,
                    variants,
                    preview_len,
                    deep_max_hits_per_file,
                    max_file_bytes,
                )
            except Exception:
                continue
            if occ <= 0:
                continue
            fuzzy_ratio_value = 0.0
            if fuzzy:
                fuzzy_ratio_value = fuzzy_best_ratio(preview, keywords, fuzzy_max_len)
                if occ <= 0 and fuzzy_ratio_value < fuzzy_threshold:
                    continue
            if occ <= 0:
                if not fuzzy:
                    continue
            deep_hits += 1
            source, weight, detail = classify_binary_target(target)
            score, coverage = score_verify_hit(
                weighted,
                len(preview),
                weight,
                len(variants_map),
                total_keywords,
                fuzzy_ratio_value,
                fuzzy_boost,
            )
            hits.append({
                "source": source.value,
                "source_detail": detail,
                "file": str(target),
                "row": 0,
                "score": score,
                "occ": occ,
                "keyword_hits": len(variants_map),
                "coverage": coverage,
                "fuzzy_ratio": fuzzy_ratio_value,
                "length": len(preview),
                "source_weight": weight,
                "preview": preview,
            })

    hits.sort(key=lambda x: x["score"], reverse=True)
    ensure_dir(out_dir)
    out_path = out_dir / f"verify_top{top_n}_{run_ts}.txt"
    csv_out_path = out_dir / f"verify_hits_{run_ts}.csv"
    try:
        with out_path.open("w", encoding="utf-8") as f:
            f.write(f"Keyword: {keyword}\n")
            f.write(f"Total hits: {len(hits)}\n\n")
            for idx, hit in enumerate(hits[:top_n], start=1):
                f.write(f"#{idx} score={hit['score']:.2f} source={hit['source']} file={hit['file']}\n")
                f.write(f"    preview={hit['preview']}\n")
    except Exception as exc:
        eprint(f"Failed to write Top-10 preview: {out_path} -> {exc}")

    try:
        with csv_out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "source",
                "source_detail",
                "file",
                "row",
                "score",
                "occ",
                "keyword_hits",
                "coverage",
                "fuzzy_ratio",
                "length",
                "source_weight",
                "preview",
            ])
            for hit in hits:
                writer.writerow([
                    hit["source"],
                    hit["source_detail"],
                    hit["file"],
                    hit["row"],
                    f"{hit['score']:.4f}",
                    hit["occ"],
                    hit["keyword_hits"],
                    f"{hit['coverage']:.4f}",
                    f"{hit['fuzzy_ratio']:.4f}",
                    hit["length"],
                    f"{hit['source_weight']:.2f}",
                    hit["preview"],
                ])
    except Exception as exc:
        eprint(f"Failed to write verification CSV: {csv_out_path} -> {exc}")

    print("One-shot verification completed.")
    if variants:
        print(f"Variant count: {len(variants)}")
    print(f"CSV rows scanned: {csv_rows_scanned} | CSV hits: {csv_hits}")
    print(f"Fragment files scanned: {blob_files_scanned} | Fragment hits: {blob_hits}")
    print(f"Plugin files scanned: {plugin_files_scanned} | Plugin hits: {plugin_hits}")
    if deep:
        print(f"Deep-scan files scanned: {deep_files_scanned} | Deep hits: {deep_hits}")
    print(f"Top-10 preview saved to: {out_path}")
    print(f"Full hit list saved to: {csv_out_path}")
