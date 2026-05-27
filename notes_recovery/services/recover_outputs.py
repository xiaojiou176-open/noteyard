from __future__ import annotations

import csv
import html
import shutil
from pathlib import Path
from typing import Callable

from notes_recovery.config import (
    RECOVER_BINARY_RAW_SLICE_BYTES,
    RECOVER_BINARY_STRINGS_MIN_LEN,
)
from notes_recovery.core.keywords import SearchVariant, fuzzy_best_ratio
from notes_recovery.core.text_bundle import markdown_escape_cell
from notes_recovery.io import ensure_dir, safe_stat_size
from notes_recovery.logging import eprint
from notes_recovery.models import BinaryHit, StitchNode, TextFragment
from notes_recovery.services.recover_sqlite import sanitize_label
from notes_recovery.utils.bytes import extract_printable_strings


def write_text_content_markdown(
    text: str,
    dst: Path,
    title: str,
    meta_lines: list[str],
    truncated: bool,
) -> None:
    ensure_dir(dst.parent)
    try:
        with dst.open("w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            for line in meta_lines:
                f.write(f"- {line}\n")
            if truncated:
                f.write("- Note: content truncated\n")
            f.write("\n```text\n")
            f.write(text)
            if text and not text.endswith("\n"):
                f.write("\n")
            f.write("```\n")
    except Exception as exc:
        eprint(f"Failed to write Markdown: {dst} -> {exc}")


def write_text_content_html(
    text: str,
    dst: Path,
    title: str,
    meta_lines: list[str],
    truncated: bool,
) -> None:
    ensure_dir(dst.parent)
    try:
        escaped = html.escape(text)
        meta_items = "\n".join(f"<li>{html.escape(line)}</li>" for line in meta_lines)
        note = "<li>Note: content truncated</li>" if truncated else ""
        html_parts = [
            "<!doctype html>",
            "<html lang=\"zh-CN\">",
            "<head>",
            "<meta charset=\"utf-8\">",
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            f"<title>{html.escape(title)}</title>",
            "<style>",
            ":root{--bg:#f7f5f2;--card:#ffffff;--text:#1f2937;--muted:#6b7280;--border:#e5e7eb}",
            "body{margin:0;background:var(--bg);color:var(--text);font-family:\"SF Pro Text\",\"PingFang SC\",\"Helvetica Neue\",Arial,sans-serif;line-height:1.6}",
            ".page{max-width:980px;margin:0 auto;padding:24px}",
            ".card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:16px}",
            "pre{white-space:pre-wrap;word-break:break-word;background:#f8fafc;border:1px solid var(--border);padding:12px;border-radius:8px}",
            "</style>",
            "</head>",
            "<body><div class=\"page\">",
            f"<h1>{html.escape(title)}</h1>",
            "<div class=\"card\"><h3>Meta</h3><ul>",
            meta_items,
            note,
            "</ul></div>",
            "<div class=\"card\"><h3>Content</h3>",
            f"<pre>{escaped}</pre>",
            "</div>",
            "</div></body></html>",
        ]
        with dst.open("w", encoding="utf-8") as f:
            f.write("\n".join(html_parts))
    except Exception as exc:
        eprint(f"Failed to write HTML: {dst} -> {exc}")


def write_text_content_txt(text: str, dst: Path) -> None:
    ensure_dir(dst.parent)
    try:
        with dst.open("w", encoding="utf-8") as f:
            f.write(text)
    except Exception as exc:
        eprint(f"Failed to write TXT: {dst} -> {exc}")


def write_fragments_outputs(
    out_dir: Path,
    fragments: list[TextFragment],
    keyword: str,
    run_ts: str,
) -> Path:
    ensure_dir(out_dir)
    manifest_path = out_dir / f"fragments_manifest_{run_ts}.csv"
    index_md = out_dir / f"fragments_index_{run_ts}.md"
    index_txt = out_dir / f"fragments_index_{run_ts}.txt"
    index_html = out_dir / f"fragments_index_{run_ts}.html"
    all_md = out_dir / f"fragments_all_{run_ts}.md"
    all_txt = out_dir / f"fragments_all_{run_ts}.txt"
    all_html = out_dir / f"fragments_all_{run_ts}.html"

    rows = []
    for idx, frag in enumerate(fragments, start=1):
        label = sanitize_label(frag.source_detail)
        base = f"fragment_{idx:04d}__{frag.source.value}__{label}_{run_ts}"
        md_path = out_dir / f"{base}.md"
        txt_path = out_dir / f"{base}.txt"
        html_path = out_dir / f"{base}.html"
        meta = [
            f"Keyword: {keyword}",
            f"Source: {frag.source.value}",
            f"Detail: {frag.source_detail}",
            f"File: {frag.file}",
            f"Occurrences: {frag.occurrences}",
            f"KeywordHits: {frag.keyword_hits}",
            f"Length: {frag.length}",
            f"Score: {frag.score:.2f}",
        ]
        write_text_content_markdown(frag.text, md_path, f"Fragment {idx}", meta, frag.truncated)
        write_text_content_txt(frag.text, txt_path)
        write_text_content_html(frag.text, html_path, f"Fragment {idx}", meta, frag.truncated)
        rows.append([
            idx,
            frag.source.value,
            frag.source_detail,
            frag.file,
            frag.occurrences,
            frag.keyword_hits,
            frag.length,
            f"{frag.score:.2f}",
            frag.truncated,
            str(md_path),
            str(txt_path),
            str(html_path),
        ])

    try:
        with manifest_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id",
                "source",
                "source_detail",
                "file",
                "occurrences",
                "keyword_hits",
                "length",
                "score",
                "truncated",
                "md_path",
                "txt_path",
                "html_path",
            ])
            writer.writerows(rows)
    except Exception as exc:
        eprint(f"Failed to write fragments manifest: {manifest_path} -> {exc}")

    try:
        with index_md.open("w", encoding="utf-8") as f:
            f.write("# Fragment Index\n\n")
            f.write(f"- Keyword: {keyword}\n")
            f.write(f"- Total: {len(fragments)}\n\n")
            f.write("| id | source | detail | occurrences | hits | length | score | md |\n")
            f.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")
            for idx, frag in enumerate(fragments, start=1):
                f.write(
                    f"| {idx} | {frag.source.value} | {markdown_escape_cell(frag.source_detail, 80)} "
                    f"| {frag.occurrences} | {frag.keyword_hits} | {frag.length} | {frag.score:.2f} "
                    f"| {idx:04d} |\n"
                )
    except Exception as exc:
        eprint(f"Failed to write fragments index Markdown: {index_md} -> {exc}")

    try:
        with index_txt.open("w", encoding="utf-8") as f:
            f.write("Fragments Index\n")
            f.write(f"Keyword: {keyword}\n")
            f.write(f"Total: {len(fragments)}\n\n")
            for idx, frag in enumerate(fragments, start=1):
                f.write(
                    f"[{idx}] {frag.source.value} occ={frag.occurrences} hits={frag.keyword_hits} "
                    f"len={frag.length} score={frag.score:.2f} detail={frag.source_detail}\n"
                )
    except Exception as exc:
        eprint(f"Failed to write fragments index TXT: {index_txt} -> {exc}")

    try:
        with index_html.open("w", encoding="utf-8") as f:
            f.write("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">")
            f.write("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
            f.write("<title>Fragments Index</title></head><body>")
            f.write(f"<h1>Fragments Index</h1><p>Keyword: {html.escape(keyword)}</p>")
            f.write(f"<p>Total: {len(fragments)}</p>")
            f.write("<table border=\"1\"><thead><tr>")
            f.write("<th>id</th><th>source</th><th>detail</th><th>occ</th><th>hits</th><th>len</th><th>score</th>")
            f.write("</tr></thead><tbody>")
            for idx, frag in enumerate(fragments, start=1):
                f.write("<tr>")
                f.write(f"<td>{idx}</td>")
                f.write(f"<td>{html.escape(frag.source.value)}</td>")
                f.write(f"<td>{html.escape(frag.source_detail)}</td>")
                f.write(f"<td>{frag.occurrences}</td>")
                f.write(f"<td>{frag.keyword_hits}</td>")
                f.write(f"<td>{frag.length}</td>")
                f.write(f"<td>{frag.score:.2f}</td>")
                f.write("</tr>")
            f.write("</tbody></table></body></html>")
    except Exception as exc:
        eprint(f"Failed to write fragments index HTML: {index_html} -> {exc}")

    try:
        with all_md.open("w", encoding="utf-8") as f:
            f.write("# Fragment Full Text\n\n")
            f.write(f"- Keyword: {keyword}\n")
            f.write(f"- Total: {len(fragments)}\n\n")
            for idx, frag in enumerate(fragments, start=1):
                f.write(f"## Fragment {idx}\n\n")
                f.write(f"- Source: {frag.source.value}\n")
                f.write(f"- Detail: {frag.source_detail}\n")
                f.write(f"- File: {frag.file}\n")
                f.write(f"- Occurrences: {frag.occurrences}\n")
                f.write(f"- KeywordHits: {frag.keyword_hits}\n")
                f.write(f"- Length: {frag.length}\n")
                f.write(f"- Score: {frag.score:.2f}\n\n")
                f.write("```text\n")
                f.write(frag.text)
                if frag.text and not frag.text.endswith("\n"):
                    f.write("\n")
                f.write("```\n\n")
    except Exception as exc:
        eprint(f"Failed to write fragments-all Markdown: {all_md} -> {exc}")

    try:
        with all_txt.open("w", encoding="utf-8") as f:
            f.write("Fragment Full Text\n")
            f.write(f"Keyword: {keyword}\n")
            f.write(f"Total: {len(fragments)}\n\n")
            for idx, frag in enumerate(fragments, start=1):
                f.write(f"[{idx}] {frag.source.value} occ={frag.occurrences} hits={frag.keyword_hits} len={frag.length} score={frag.score:.2f}\n")
                f.write(frag.text)
                if frag.text and not frag.text.endswith("\n"):
                    f.write("\n")
                f.write("\n")
    except Exception as exc:
        eprint(f"Failed to write fragments-all TXT: {all_txt} -> {exc}")

    try:
        with all_html.open("w", encoding="utf-8") as f:
            f.write("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">")
            f.write("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
            f.write("<title>Fragments All</title></head><body>")
            f.write(f"<h1>Fragments All</h1><p>Keyword: {html.escape(keyword)}</p>")
            f.write(f"<p>Total: {len(fragments)}</p>")
            for idx, frag in enumerate(fragments, start=1):
                f.write(f"<h2>Fragment {idx}</h2>")
                f.write("<ul>")
                f.write(f"<li>Source: {html.escape(frag.source.value)}</li>")
                f.write(f"<li>Detail: {html.escape(frag.source_detail)}</li>")
                f.write(f"<li>File: {html.escape(frag.file)}</li>")
                f.write(f"<li>Occurrences: {frag.occurrences}</li>")
                f.write(f"<li>KeywordHits: {frag.keyword_hits}</li>")
                f.write(f"<li>Length: {frag.length}</li>")
                f.write(f"<li>Score: {frag.score:.2f}</li>")
                f.write("</ul>")
                f.write("<pre>")
                f.write(html.escape(frag.text))
                f.write("</pre>")
            f.write("</body></html>")
    except Exception as exc:
        eprint(f"Failed to write fragments-all HTML: {all_html} -> {exc}")

    return manifest_path


def write_stitched_outputs(
    out_dir: Path,
    nodes: list[StitchNode],
    keyword: str,
    run_ts: str,
    variants_map: dict[str, list[SearchVariant]],
    *,
    score_hit_fn: Callable[[float, int, float], float],
    compute_stitch_confidence_fn: Callable[[StitchNode], float],
) -> Path:
    ensure_dir(out_dir)
    manifest_path = out_dir / f"stitched_manifest_{run_ts}.csv"
    index_md = out_dir / f"stitched_index_{run_ts}.md"
    index_txt = out_dir / f"stitched_index_{run_ts}.txt"
    index_html = out_dir / f"stitched_index_{run_ts}.html"

    rows = []
    for idx, node in enumerate(nodes, start=1):
        label = sanitize_label("__".join(sorted(node.sources)))
        base = f"stitched_{idx:04d}__{label}_{run_ts}"
        md_path = out_dir / f"{base}.md"
        txt_path = out_dir / f"{base}.txt"
        html_path = out_dir / f"{base}.html"
        score = score_hit_fn(float(node.overlap_total), len(node.text), 1.0)
        fuzzy = fuzzy_best_ratio(node.text, list(variants_map.keys()), 2000)
        confidence = compute_stitch_confidence_fn(node)
        meta = [
            f"Keyword: {keyword}",
            f"Sources: {', '.join(sorted(node.sources))}",
            f"FragmentIDs: {node.fragment_ids}",
            f"Cluster: {node.cluster_id}",
            f"Merges: {node.merge_count}",
            f"OverlapTotal: {node.overlap_total}",
            f"Length: {len(node.text)}",
            f"Score: {score:.2f}",
            f"Fuzzy: {fuzzy:.2f}",
            f"Confidence: {confidence:.2f}",
        ]
        write_text_content_markdown(node.text, md_path, f"Stitched {idx}", meta, False)
        write_text_content_txt(node.text, txt_path)
        write_text_content_html(node.text, html_path, f"Stitched {idx}", meta, False)
        rows.append([
            idx,
            ",".join(sorted(node.sources)),
            ",".join(str(x) for x in node.fragment_ids),
            node.cluster_id,
            node.merge_count,
            node.overlap_total,
            len(node.text),
            f"{score:.2f}",
            f"{fuzzy:.2f}",
            f"{confidence:.2f}",
            str(md_path),
            str(txt_path),
            str(html_path),
        ])

    try:
        with manifest_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id",
                "sources",
                "fragment_ids",
                "cluster_id",
                "merge_count",
                "overlap_total",
                "length",
                "score",
                "fuzzy",
                "confidence",
                "md_path",
                "txt_path",
                "html_path",
            ])
            writer.writerows(rows)
    except Exception as exc:
        eprint(f"Failed to write stitched manifest: {manifest_path} -> {exc}")

    try:
        with index_md.open("w", encoding="utf-8") as f:
            f.write("# Stitched Index\n\n")
            f.write(f"- Keyword: {keyword}\n")
            f.write(f"- Total: {len(nodes)}\n\n")
            f.write("| id | sources | fragments | length | score | fuzzy | confidence | md |\n")
            f.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")
            for idx, node in enumerate(nodes, start=1):
                sources = ", ".join(sorted(node.sources))
                f.write(
                    f"| {idx} | {markdown_escape_cell(sources, 80)} | {len(node.fragment_ids)} | {len(node.text)} "
                    f"| {score_hit_fn(float(node.overlap_total), len(node.text), 1.0):.2f} "
                    f"| {fuzzy_best_ratio(node.text, list(variants_map.keys()), 2000):.2f} "
                    f"| {compute_stitch_confidence_fn(node):.2f} | {idx:04d} |\n"
                )
    except Exception as exc:
        eprint(f"Failed to write stitched index Markdown: {index_md} -> {exc}")

    try:
        with index_txt.open("w", encoding="utf-8") as f:
            f.write("Stitched Index\n")
            f.write(f"Keyword: {keyword}\n")
            f.write(f"Total: {len(nodes)}\n\n")
            for idx, node in enumerate(nodes, start=1):
                sources = ", ".join(sorted(node.sources))
                f.write(
                    f"[{idx}] sources={sources} fragments={len(node.fragment_ids)} len={len(node.text)} "
                    f"score={score_hit_fn(float(node.overlap_total), len(node.text), 1.0):.2f} "
                    f"fuzzy={fuzzy_best_ratio(node.text, list(variants_map.keys()), 2000):.2f} "
                    f"confidence={compute_stitch_confidence_fn(node):.2f}\n"
                )
    except Exception as exc:
        eprint(f"Failed to write stitched index TXT: {index_txt} -> {exc}")

    try:
        with index_html.open("w", encoding="utf-8") as f:
            f.write("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">")
            f.write("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
            f.write("<title>Stitched Index</title></head><body>")
            f.write(f"<h1>Stitched Index</h1><p>Keyword: {html.escape(keyword)}</p>")
            f.write(f"<p>Total: {len(nodes)}</p>")
            f.write("<table border=\"1\"><thead><tr>")
            f.write("<th>id</th><th>sources</th><th>fragments</th><th>length</th><th>score</th><th>fuzzy</th><th>confidence</th>")
            f.write("</tr></thead><tbody>")
            for idx, node in enumerate(nodes, start=1):
                sources = ", ".join(sorted(node.sources))
                f.write("<tr>")
                f.write(f"<td>{idx}</td>")
                f.write(f"<td>{html.escape(sources)}</td>")
                f.write(f"<td>{len(node.fragment_ids)}</td>")
                f.write(f"<td>{len(node.text)}</td>")
                f.write(f"<td>{score_hit_fn(float(node.overlap_total), len(node.text), 1.0):.2f}</td>")
                f.write(f"<td>{fuzzy_best_ratio(node.text, list(variants_map.keys()), 2000):.2f}</td>")
                f.write(f"<td>{compute_stitch_confidence_fn(node):.2f}</td>")
                f.write("</tr>")
            f.write("</tbody></table></body></html>")
    except Exception as exc:
        eprint(f"Failed to write stitched index HTML: {index_html} -> {exc}")

    return manifest_path


def collect_sidecar_paths(path: Path) -> list[Path]:
    sidecars: list[Path] = []
    for suffix in (".md", ".txt", ".html"):
        candidate = path.with_suffix(suffix)
        if candidate.exists():
            sidecars.append(candidate)
    return sidecars


def write_binary_hits_outputs(
    out_dir: Path,
    hits: list[BinaryHit],
    keyword: str,
    run_ts: str,
    preview_bytes: int,
    max_chars: int,
    max_copy_mb: int,
    raw_slice_bytes: int = RECOVER_BINARY_RAW_SLICE_BYTES,
) -> None:
    ensure_dir(out_dir)
    manifest_path = out_dir / f"binary_hits_{run_ts}.csv"
    index_md = out_dir / f"binary_hits_{run_ts}.md"
    index_txt = out_dir / f"binary_hits_{run_ts}.txt"
    all_md = out_dir / f"binary_hits_all_{run_ts}.md"
    all_txt = out_dir / f"binary_hits_all_{run_ts}.txt"

    rows = []
    for idx, hit in enumerate(hits, start=1):
        preview_path = out_dir / f"binary_preview_{idx:04d}_{run_ts}.txt"
        with preview_path.open("w", encoding="utf-8") as f:
            preview = extract_printable_strings(hit.path, RECOVER_BINARY_STRINGS_MIN_LEN, max_chars)
            f.write(preview)
        raw_slice_path = out_dir / f"binary_raw_{idx:04d}_{run_ts}.bin"
        try:
            with hit.path.open("rb") as f:
                f.seek(hit.offsets[0])
                chunk = f.read(raw_slice_bytes)
            with raw_slice_path.open("wb") as f:
                f.write(chunk)
        except Exception:
            raw_slice_path = Path("")

        copy_path = ""
        if max_copy_mb <= 0 or safe_stat_size(hit.path) <= max_copy_mb * 1024 * 1024:
            try:
                copy_dst = out_dir / f"binary_copy_{idx:04d}_{run_ts}{hit.path.suffix}"
                shutil.copy2(hit.path, copy_dst)
                copy_path = str(copy_dst)
            except Exception:
                copy_path = ""
        rows.append([
            idx,
            hit.weighted,
            hit.path.name,
            safe_stat_size(hit.path),
            ",".join(str(o) for o in hit.offsets),
            hit.source_detail,
            str(preview_path),
            str(raw_slice_path) if raw_slice_path else "",
            copy_path,
        ])

    try:
        with manifest_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id",
                "weighted",
                "file",
                "bytes",
                "offsets",
                "source_detail",
                "preview_path",
                "raw_slice_path",
                "copy_path",
            ])
            writer.writerows(rows)
    except Exception as exc:
        eprint(f"Failed to write binary hits CSV: {manifest_path} -> {exc}")

    try:
        with index_md.open("w", encoding="utf-8") as f:
            f.write("# Binary Hits\n\n")
            f.write(f"- Keyword: {keyword}\n")
            f.write(f"- Total: {len(rows)}\n\n")
            f.write("| id | weighted | file | bytes | offsets | preview |\n")
            f.write("| --- | --- | --- | --- | --- | --- |\n")
            for row in rows:
                f.write(
                    f"| {row[0]} | {row[1]:.2f} | {markdown_escape_cell(row[2], 60)} | {row[3]} "
                    f"| {markdown_escape_cell(row[4], 60)} | {markdown_escape_cell(row[6], 80)} |\n"
                )
    except Exception as exc:
        eprint(f"Failed to write binary hits Markdown: {index_md} -> {exc}")

    try:
        with index_txt.open("w", encoding="utf-8") as f:
            f.write("Binary Hits\n")
            f.write(f"Keyword: {keyword}\n")
            f.write(f"Total: {len(rows)}\n\n")
            for row in rows:
                f.write(f"[{row[0]}] {row[1]:.2f} file={row[2]} size={row[3]} offsets={row[4]}\n")
    except Exception as exc:
        eprint(f"Failed to write binary hits TXT: {index_txt} -> {exc}")

    try:
        with all_md.open("w", encoding="utf-8") as f:
            f.write("# Binary Hits Full Text\n\n")
            f.write(f"- Keyword: {keyword}\n")
            f.write(f"- Total: {len(rows)}\n\n")
            for row in rows:
                f.write(f"## Hit {row[0]}\n\n")
                f.write(f"- Weighted: {row[1]:.2f}\n")
                f.write(f"- File: {row[2]}\n")
                f.write(f"- Bytes: {row[3]}\n")
                f.write(f"- Offsets: {row[4]}\n")
                f.write(f"- Preview: {row[6]}\n")
                f.write("\n```text\n")
                try:
                    content = Path(row[6]).read_text(encoding="utf-8")
                except Exception:
                    content = ""
                f.write(content)
                if content and not content.endswith("\n"):
                    f.write("\n")
                f.write("```\n\n")
    except Exception as exc:
        eprint(f"Failed to write binary-all Markdown: {all_md} -> {exc}")

    try:
        with all_txt.open("w", encoding="utf-8") as f:
            f.write("Binary Hits Summary\n")
            f.write(f"Keyword: {keyword}\n")
            f.write(f"Total: {len(rows)}\n\n")
            for row in rows:
                f.write(f"[{row[0]}] {row[1]} file={row[2]} size={row[3]} offsets={row[4]}\n")
                txt_path = Path(row[6])
                try:
                    content = txt_path.read_text(encoding="utf-8")
                except Exception:
                    content = ""
                if content:
                    f.write(content)
                    if not content.endswith("\n"):
                        f.write("\n")
                f.write("\n")
    except Exception as exc:
        eprint(f"Failed to write binary-all TXT: {all_txt} -> {exc}")
