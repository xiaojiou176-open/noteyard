from __future__ import annotations

import csv
import hashlib
import json
import shutil
import struct
from pathlib import Path
from typing import Any, Iterable, Optional

from notes_recovery.case_contract import (
    CASE_DIR_DB_BACKUP,
    CASE_DIR_WAL_ISOLATION,
    CASE_FILE_NOTESTORE_SHM,
    CASE_FILE_NOTESTORE_WAL,
    case_dir,
)
from notes_recovery.config import DEFAULT_PATHS, WAL_FRAME_HEADER_SIZE, WAL_HEADER_SIZE, WAL_MAGIC_BE, WAL_MAGIC_LE
from notes_recovery.core.binary import decode_carved_payload
from notes_recovery.core.keywords import count_occurrences_for_keywords, split_keywords
from notes_recovery.io import ensure_dir, is_within, require_non_negative_int, require_positive_int
from notes_recovery.logging import log_warn
from notes_recovery.models import WalAction
from notes_recovery.services.recover import sanitize_label, write_text_content_markdown, write_text_content_txt


def wal_isolate(target_dir: Path, action: WalAction, isolate_dir_name: str, allow_original: bool) -> None:
    target_dir = target_dir.resolve()
    isolate_dir = target_dir / isolate_dir_name
    ensure_dir(isolate_dir)

    wal = target_dir / CASE_FILE_NOTESTORE_WAL
    shm = target_dir / CASE_FILE_NOTESTORE_SHM

    original_root = DEFAULT_PATHS.notes_group_container.expanduser().resolve()
    if not allow_original and is_within(target_dir, original_root) and action != WalAction.COPY_ONLY:
        raise RuntimeError(
            "To preserve the evidence chain, modifying the original Notes database is disabled by default. "
            "Run snapshot first to work on a copy, or pass --allow-original to override explicitly."
        )

    if action == WalAction.COPY_ONLY:
        try:
            if wal.exists():
                shutil.copy2(wal, isolate_dir / wal.name)
            if shm.exists():
                shutil.copy2(shm, isolate_dir / shm.name)
        except Exception as exc:
            raise RuntimeError(f"Failed to copy WAL/SHM files: {exc}")
        print(f"Copied WAL/SHM files -> {isolate_dir}")
        return

    if action == WalAction.ISOLATE:
        try:
            if wal.exists():
                shutil.move(wal, isolate_dir / wal.name)
            if shm.exists():
                shutil.move(shm, isolate_dir / shm.name)
        except Exception as exc:
            raise RuntimeError(f"Failed to isolate WAL/SHM files: {exc}")
        print(f"Isolated WAL/SHM files -> {isolate_dir}")
        return

    if action == WalAction.RESTORE:
        wal_src = isolate_dir / wal.name
        shm_src = isolate_dir / shm.name
        try:
            if wal_src.exists():
                shutil.move(wal_src, target_dir / wal.name)
            if shm_src.exists():
                shutil.move(shm_src, target_dir / shm.name)
        except Exception as exc:
            raise RuntimeError(f"Failed to restore WAL/SHM files: {exc}")
        print(f"Restored WAL/SHM files -> {target_dir}")
        return

    raise RuntimeError(f"Unknown WAL action: {action}")


def is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def parse_wal_header(path: Path, page_size_override: int) -> dict[str, Any]:
    try:
        with path.open("rb") as f:
            header = f.read(WAL_HEADER_SIZE)
    except Exception as exc:
        raise RuntimeError(f"Failed to read WAL file: {path} -> {exc}")
    if len(header) < WAL_HEADER_SIZE:
        raise RuntimeError(f"WAL header is truncated: {path}")

    magic = struct.unpack(">I", header[0:4])[0]
    if magic not in (WAL_MAGIC_BE, WAL_MAGIC_LE):
        raise RuntimeError(f"Unexpected WAL magic: {path} magic=0x{magic:08x}")
    endian = ">" if magic == WAL_MAGIC_BE else "<"
    fmt = f"{endian}7I"
    (
        version,
        page_size_raw,
        checkpoint_seq,
        salt1,
        salt2,
        checksum1,
        checksum2,
    ) = struct.unpack(fmt, header[4:32])
    if page_size_override > 0:
        page_size = page_size_override
    else:
        if page_size_raw == 0:
            page_size = 65536
        elif page_size_raw < 512 or page_size_raw > 65536 or not is_power_of_two(page_size_raw):
            raise RuntimeError(
                f"Unexpected WAL page size: {page_size_raw}. "
                "Use --page-size to override it manually."
            )
        else:
            page_size = page_size_raw

    return {
        "magic": f"0x{magic:08x}",
        "endian": "big" if endian == ">" else "little",
        "version": version,
        "page_size_raw": page_size_raw,
        "page_size": page_size,
        "checkpoint_seq": checkpoint_seq,
        "salt1": salt1,
        "salt2": salt2,
        "checksum1": checksum1,
        "checksum2": checksum2,
    }


def count_wal_page_occurrences(
    path: Path,
    page_size: int,
    endian: str,
    max_frames: int,
) -> tuple[dict[int, int], int, int]:
    counts: dict[int, int] = {}
    frame_count = 0
    file_size = 0
    try:
        file_size = path.stat().st_size
        with path.open("rb") as f:
            offset = WAL_HEADER_SIZE
            while offset + WAL_FRAME_HEADER_SIZE + page_size <= file_size:
                if frame_count >= max_frames:
                    break
                f.seek(offset)
                header = f.read(WAL_FRAME_HEADER_SIZE)
                if len(header) < WAL_FRAME_HEADER_SIZE:
                    break
                page_no = struct.unpack(f"{endian}I", header[0:4])[0]
                counts[page_no] = counts.get(page_no, 0) + 1
                offset += WAL_FRAME_HEADER_SIZE + page_size
                frame_count += 1
    except Exception as exc:
        raise RuntimeError(f"Failed to count WAL frames: {path} -> {exc}")

    trailing = max(0, file_size - (WAL_HEADER_SIZE + frame_count * (WAL_FRAME_HEADER_SIZE + page_size)))
    return counts, frame_count, trailing


def iter_wal_frames(
    path: Path,
    page_size: int,
    endian: str,
    max_frames: int,
) -> Iterable[dict[str, Any]]:
    try:
        file_size = path.stat().st_size
        with path.open("rb") as f:
            offset = WAL_HEADER_SIZE
            frame_index = 0
            while offset + WAL_FRAME_HEADER_SIZE + page_size <= file_size:
                if frame_index >= max_frames:
                    break
                f.seek(offset)
                header = f.read(WAL_FRAME_HEADER_SIZE)
                if len(header) < WAL_FRAME_HEADER_SIZE:
                    break
                (
                    page_no,
                    db_size,
                    salt1,
                    salt2,
                    checksum1,
                    checksum2,
                ) = struct.unpack(f"{endian}6I", header)
                data = f.read(page_size)
                if len(data) < page_size:
                    break
                frame_index += 1
                yield {
                    "frame_index": frame_index,
                    "offset": offset,
                    "page_no": page_no,
                    "db_size": db_size,
                    "salt1": salt1,
                    "salt2": salt2,
                    "checksum1": checksum1,
                    "checksum2": checksum2,
                    "data": data,
                }
                offset += WAL_FRAME_HEADER_SIZE + page_size
    except Exception as exc:
        raise RuntimeError(f"Failed to iterate WAL frames: {path} -> {exc}")


def collect_wal_files(root_dir: Path) -> list[Path]:
    wal_files: list[Path] = []
    db_dir = case_dir(root_dir, CASE_DIR_DB_BACKUP)
    wal = db_dir / CASE_FILE_NOTESTORE_WAL
    if wal.exists():
        wal_files.append(wal)
    wal_isolation = case_dir(db_dir, CASE_DIR_WAL_ISOLATION)
    if wal_isolation.exists():
        wal_files.extend(sorted(wal_isolation.glob("*.sqlite-wal")))
    return wal_files


def wal_extract(
    root_dir: Path,
    out_dir: Path,
    keyword: Optional[str],
    max_frames: int,
    page_size_override: int,
    dump_pages: bool,
    dump_only_duplicates: bool,
    strings_on: bool,
    strings_min_len: int,
    strings_max_chars: int,
    run_ts: str,
    wal_path: Optional[Path] = None,
) -> Path:
    require_positive_int(max_frames, "WAL max frame count")
    require_non_negative_int(page_size_override, "WAL page-size override")
    require_positive_int(strings_min_len, "WAL minimum string length")
    require_positive_int(strings_max_chars, "WAL maximum string character count")
    ensure_dir(out_dir)
    keywords = split_keywords(keyword)

    wal_files: list[Path] = []
    if wal_path:
        wal_files = [wal_path]
    else:
        wal_files = collect_wal_files(root_dir)
    if not wal_files:
        raise RuntimeError("No WAL file was found. Confirm that Notes_Forensics/DB_Backup or WAL_Isolation exists.")

    manifest_paths: list[str] = []
    for wal_file in wal_files:
        if not wal_file.exists():
            log_warn(f"Skipping missing WAL file: {wal_file}")
            continue
        header = parse_wal_header(wal_file, page_size_override)
        endian = ">" if header["endian"] == "big" else "<"
        page_size = int(header["page_size"])
        page_counts, frame_count, trailing = count_wal_page_occurrences(
            wal_file, page_size, endian, max_frames
        )

        wal_label = sanitize_label(wal_file.name)
        wal_out_dir = out_dir / wal_label
        ensure_dir(wal_out_dir)
        pages_dir = wal_out_dir / "Pages"
        strings_dir = wal_out_dir / "Strings"
        if dump_pages:
            ensure_dir(pages_dir)
        if strings_on:
            ensure_dir(strings_dir)

        header_payload = dict(header)
        header_payload.update(
            {
                "wal_file": str(wal_file),
                "file_size": wal_file.stat().st_size,
                "frame_count": frame_count,
                "max_frames": max_frames,
                "trailing_bytes": trailing,
            }
        )
        header_path = wal_out_dir / "wal_header.json"
        try:
            with header_path.open("w", encoding="utf-8") as f:
                json.dump(header_payload, f, ensure_ascii=True, indent=2)
        except Exception as exc:
            log_warn(f"Failed to write WAL header: {header_path} -> {exc}")

        manifest_path = wal_out_dir / f"wal_frames_{run_ts}.csv"
        manifest_paths.append(str(manifest_path))
        rows: list[list[Any]] = []
        version_counts: dict[int, int] = {}

        for frame in iter_wal_frames(wal_file, page_size, endian, max_frames):
            page_no = int(frame["page_no"])
            version_counts[page_no] = version_counts.get(page_no, 0) + 1
            version_idx = version_counts[page_no]
            is_duplicate = page_counts.get(page_no, 0) > 1
            should_dump = dump_pages and (not dump_only_duplicates or is_duplicate)
            page_dump_path = ""
            strings_path = ""
            strings_md_path = ""
            strings_label = ""
            strings_len = 0
            keyword_hits = 0

            payload = frame["data"]
            if strings_on or keywords:
                text, strings_label = decode_carved_payload(payload, strings_max_chars)
                if text:
                    strings_len = len(text)
                if keywords and text:
                    keyword_hits = count_occurrences_for_keywords(text, keywords)

                if strings_on and text:
                    base_name = (
                        f"wal_frame_{frame['frame_index']:06d}"
                        f"_page_{page_no:06d}"
                        f"_v{version_idx:03d}_{run_ts}"
                    )
                    strings_path = str(strings_dir / f"{base_name}.txt")
                    strings_md_path = str(strings_dir / f"{base_name}.md")
                    meta = [
                        f"WAL: {wal_file.name}",
                        f"Frame: {frame['frame_index']}",
                        f"Page: {page_no} (v{version_idx})",
                        f"PageSize: {page_size}",
                        f"DbSize: {frame['db_size']}",
                        f"Offset: {frame['offset']}",
                        f"Encoding: {strings_label}",
                        f"KeywordHits: {keyword_hits}",
                    ]
                    write_text_content_txt(text, Path(strings_path))
                    write_text_content_markdown(
                        text,
                        Path(strings_md_path),
                        f"WAL Frame {frame['frame_index']} Page {page_no}",
                        meta,
                        len(text) >= strings_max_chars,
                    )

            if should_dump:
                base_name = (
                    f"wal_frame_{frame['frame_index']:06d}"
                    f"_page_{page_no:06d}"
                    f"_v{version_idx:03d}.bin"
                )
                page_dump_path = str(pages_dir / base_name)
                try:
                    with Path(page_dump_path).open("wb") as f:
                        f.write(payload)
                except Exception as exc:
                    log_warn(f"Failed to write WAL page dump: {page_dump_path} -> {exc}")
                    page_dump_path = ""

            rows.append(
                [
                    wal_file.name,
                    frame["frame_index"],
                    page_no,
                    version_idx,
                    frame["db_size"],
                    int(frame["db_size"] > 0),
                    frame["salt1"],
                    frame["salt2"],
                    frame["checksum1"],
                    frame["checksum2"],
                    frame["offset"],
                    page_size,
                    int(is_duplicate),
                    keyword_hits,
                    strings_label,
                    strings_len,
                    strings_path,
                    strings_md_path,
                    page_dump_path,
                ]
            )

        try:
            with manifest_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "wal_file",
                        "frame_index",
                        "page_no",
                        "page_version",
                        "db_size",
                        "is_commit",
                        "salt1",
                        "salt2",
                        "checksum1",
                        "checksum2",
                        "offset",
                        "page_size",
                        "is_duplicate",
                        "keyword_hits",
                        "strings_label",
                        "strings_len",
                        "strings_path",
                        "strings_md_path",
                        "page_dump_path",
                    ]
                )
                writer.writerows(rows)
        except Exception as exc:
            raise RuntimeError(f"Failed to write WAL manifest: {manifest_path} -> {exc}")

        summary_path = wal_out_dir / f"wal_summary_{run_ts}.md"
        try:
            with summary_path.open("w", encoding="utf-8") as f:
                f.write("# WAL Deep Analysis Summary\n\n")
                f.write(f"- WAL: {wal_file}\n")
                f.write(f"- Frames: {len(rows)}\n")
                f.write(f"- Duplicated Pages: {sum(1 for v in page_counts.values() if v > 1)}\n")
                f.write(f"- Trailing Bytes: {trailing}\n")
                f.write(f"- Manifest: {manifest_path}\n")
                if dump_pages:
                    f.write(f"- Pages Dir: {pages_dir}\n")
                if strings_on:
                    f.write(f"- Strings Dir: {strings_dir}\n")
        except Exception as exc:
            log_warn(f"Failed to write WAL summary: {summary_path} -> {exc}")

    meta_path = out_dir / f"wal_extract_manifest_{run_ts}.json"
    try:
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "root_dir": str(root_dir),
                    "wal_files": [str(p) for p in wal_files],
                    "manifests": manifest_paths,
                    "keyword": keyword or "",
                    "dump_pages": dump_pages,
                    "dump_only_duplicates": dump_only_duplicates,
                    "strings_on": strings_on,
                },
                f,
                ensure_ascii=True,
                indent=2,
            )
    except Exception as exc:
        log_warn(f"Failed to write WAL top-level manifest: {meta_path} -> {exc}")

    return meta_path


def build_wal_frame_index(
    path: Path,
    page_size_override: int,
    max_frames: int,
) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    header = parse_wal_header(path, page_size_override)
    endian = ">" if header["endian"] == "big" else "<"
    page_size = int(header["page_size"])
    index: dict[int, dict[str, Any]] = {}
    for frame in iter_wal_frames(path, page_size, endian, max_frames):
        page_no = int(frame["page_no"])
        payload = frame["data"]
        digest = hashlib.sha256(payload).hexdigest()
        entry = index.get(page_no, {"count": 0})
        entry.update(
            {
                "count": entry.get("count", 0) + 1,
                "last_frame_index": frame["frame_index"],
                "last_offset": frame["offset"],
                "last_checksum1": frame["checksum1"],
                "last_checksum2": frame["checksum2"],
                "last_db_size": frame["db_size"],
                "last_hash": digest,
            }
        )
        index[page_no] = entry
    return header, index


def wal_diff(
    wal_a: Path,
    wal_b: Path,
    out_dir: Path,
    max_frames: int,
    page_size_override: int,
    run_ts: str,
) -> Path:
    require_positive_int(max_frames, "WAL diff max frame count")
    require_non_negative_int(page_size_override, "WAL page-size override")
    ensure_dir(out_dir)
    header_a, index_a = build_wal_frame_index(wal_a, page_size_override, max_frames)
    header_b, index_b = build_wal_frame_index(wal_b, page_size_override, max_frames)
    if header_a["page_size"] != header_b["page_size"]:
        raise RuntimeError(
            f"WAL page size mismatch: {wal_a}={header_a['page_size']} {wal_b}={header_b['page_size']}"
        )

    rows: list[list[Any]] = []
    pages = sorted(set(index_a.keys()) | set(index_b.keys()))
    changed = 0
    added = 0
    removed = 0
    same = 0
    for page_no in pages:
        a = index_a.get(page_no)
        b = index_b.get(page_no)
        status = "changed"
        if a and not b:
            status = "removed"
            removed += 1
        elif b and not a:
            status = "added"
            added += 1
        else:
            if a and b and a.get("last_hash") == b.get("last_hash"):
                status = "same"
                same += 1
            else:
                changed += 1
        rows.append(
            [
                page_no,
                status,
                a.get("count") if a else 0,
                b.get("count") if b else 0,
                a.get("last_frame_index") if a else 0,
                b.get("last_frame_index") if b else 0,
                a.get("last_hash") if a else "",
                b.get("last_hash") if b else "",
                a.get("last_checksum1") if a else 0,
                b.get("last_checksum1") if b else 0,
                a.get("last_checksum2") if a else 0,
                b.get("last_checksum2") if b else 0,
            ]
        )

    diff_csv = out_dir / f"wal_diff_{run_ts}.csv"
    diff_json = out_dir / f"wal_diff_{run_ts}.json"
    try:
        with diff_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "page_no",
                    "status",
                    "count_a",
                    "count_b",
                    "last_frame_a",
                    "last_frame_b",
                    "hash_a",
                    "hash_b",
                    "checksum1_a",
                    "checksum1_b",
                    "checksum2_a",
                    "checksum2_b",
                ]
            )
            writer.writerows(rows)
    except Exception as exc:
        raise RuntimeError(f"Failed to write WAL diff CSV: {diff_csv} -> {exc}")

    try:
        with diff_json.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "wal_a": str(wal_a),
                    "wal_b": str(wal_b),
                    "page_size": header_a["page_size"],
                    "total_pages": len(pages),
                    "added": added,
                    "removed": removed,
                    "changed": changed,
                    "same": same,
                },
                f,
                ensure_ascii=True,
                indent=2,
            )
    except Exception as exc:
        log_warn(f"Failed to write WAL diff JSON: {diff_json} -> {exc}")

    return diff_json
