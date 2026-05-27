from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from notes_recovery.case_contract import (
    CASE_DIR_CACHE_BACKUP,
    CASE_DIR_DB_BACKUP,
    CASE_DIR_SPOTLIGHT_BACKUP,
    CASE_FILE_NOTESTORE_SQLITE,
    case_dir,
)
from notes_recovery.config import DEFAULT_PATHS
from notes_recovery.core.pipeline import collect_snapshot_hash_targets, timestamp_now, write_hash_manifest
from notes_recovery.io import ensure_dir, ensure_safe_output_dir
from notes_recovery.logging import eprint


def warn_if_notes_running() -> None:
    try:
        completed = subprocess.run(
            ["/usr/bin/pgrep", "-x", "Notes"],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            eprint("Reminder: Notes appears to be running. Quit Notes before continuing so the evidence copy does not change underneath the workflow.")
    except Exception:
        return


def run_cmd(cmd: list[str]) -> None:
    try:
        completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if completed.stdout:
            print(completed.stdout.strip())
        if completed.stderr:
            eprint(completed.stderr.strip())
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Command failed: {' '.join(cmd)} -> {exc.stderr}")


def copy_with_ditto(src: Path, dst: Path) -> None:
    cmd = ["/usr/bin/ditto", "-V", str(src), str(dst)]
    run_cmd(cmd)


def copy_tree_fallback(src: Path, dst: Path) -> None:
    try:
        shutil.copytree(src, dst, dirs_exist_ok=True)
    except Exception as exc:
        raise RuntimeError(f"copytree failed: {src} -> {dst} -> {exc}")


def copy_path(src: Path, dst: Path) -> None:
    if not src.exists():
        raise RuntimeError(f"Source path does not exist: {src}")
    ensure_dir(dst)
    try:
        copy_with_ditto(src, dst)
    except Exception:
        copy_tree_fallback(src, dst)


def snapshot(out_dir: Path, include_core_spotlight: bool, include_notes_cache: bool, run_ts: Optional[str] = None) -> None:
    ensure_safe_output_dir(
        out_dir,
        [
            DEFAULT_PATHS.notes_group_container,
            DEFAULT_PATHS.core_spotlight,
            DEFAULT_PATHS.notes_cache,
        ],
        "Snapshot",
    )
    ensure_dir(out_dir)
    if not run_ts:
        run_ts = timestamp_now()
    warn_if_notes_running()

    notes_dst = case_dir(out_dir, CASE_DIR_DB_BACKUP)
    copy_path(DEFAULT_PATHS.notes_group_container.expanduser(), notes_dst)
    print(f"Copied Notes group container -> {notes_dst}")
    if not (notes_dst / CASE_FILE_NOTESTORE_SQLITE).exists():
        eprint("Warning: NoteStore.sqlite was not found in the copied evidence. Confirm that the Notes database path exists on this host.")

    if include_core_spotlight:
        spotlight_dst = case_dir(out_dir, CASE_DIR_SPOTLIGHT_BACKUP)
        copy_path(DEFAULT_PATHS.core_spotlight.expanduser(), spotlight_dst)
        print(f"Copied CoreSpotlight index -> {spotlight_dst}")

    if include_notes_cache:
        cache_dst = case_dir(out_dir, CASE_DIR_CACHE_BACKUP)
        copy_path(DEFAULT_PATHS.notes_cache.expanduser(), cache_dst)
        print(f"Copied Notes cache -> {cache_dst}")

    hash_targets = collect_snapshot_hash_targets(out_dir)
    manifest_path = write_hash_manifest(out_dir, run_ts, hash_targets, "snapshot")
    if manifest_path:
        print(f"Hash manifest written: {manifest_path}")
