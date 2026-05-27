from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Optional

from notes_recovery.core.pipeline import timestamp_now
from notes_recovery.core.text_bundle import flatten_safe_name, shorten_name_if_needed, unique_name
from notes_recovery.io import ensure_dir, is_within


def flatten_backup(src_dir: Path, out_dir: Path, include_manifest: bool = True, run_ts: Optional[str] = None) -> None:
    if not src_dir.exists():
        raise RuntimeError(f"Source directory does not exist: {src_dir}")
    if src_dir.resolve() == out_dir.resolve():
        raise RuntimeError("The output directory must not match the source directory.")
    if is_within(out_dir, src_dir):
        raise RuntimeError("The output directory must not be inside the source directory.")

    ensure_dir(out_dir)
    seen: dict[str, int] = {}
    manifest_rows: list[tuple[str, str, str, int]] = []

    for path in sorted(src_dir.rglob("*")):
        is_link = path.is_symlink()
        if not is_link and path.is_dir():
            continue
        if is_within(path, out_dir):
            continue

        rel = path.relative_to(src_dir)
        parts = rel.parts
        if len(parts) > 1:
            category = parts[0]
            sub_parts = parts[1:]
        else:
            category = "ROOT"
            sub_parts = parts

        sub_name = "__".join(sub_parts) if sub_parts else ""
        flat_name = f"{category}__{sub_name}" if sub_name else category
        flat_name = flatten_safe_name(flat_name)
        flat_name = shorten_name_if_needed(flat_name)
        flat_name = unique_name(flat_name, seen)

        dest = out_dir / flat_name
        try:
            if is_link:
                shutil.copy2(path, dest, follow_symlinks=False)
            else:
                shutil.copy2(path, dest)
        except Exception as exc:
            raise RuntimeError(f"Copy failed: {path} -> {dest} -> {exc}")

        try:
            size = path.lstat().st_size
        except Exception:
            size = 0
        manifest_rows.append((flat_name, category, str(rel), size))

    if include_manifest:
        if not run_ts:
            run_ts = timestamp_now()
        manifest_name = f"flatten_manifest_{run_ts}.csv" if run_ts else "flatten_manifest.csv"
        manifest_path = out_dir / manifest_name
        try:
            with manifest_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["flat_name", "category", "source_relpath", "bytes"])
                writer.writerows(manifest_rows)
        except Exception as exc:
            raise RuntimeError(f"Failed to write manifest: {manifest_path} -> {exc}")
