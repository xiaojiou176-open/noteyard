from __future__ import annotations

from pathlib import Path

from notes_recovery.case_contract import (
    CASE_DIR_CACHE_BACKUP,
    CASE_DIR_DB_BACKUP,
    CASE_DIR_RECOVERED_DB,
    CASE_DIR_SPOTLIGHT_BACKUP,
    CASE_ROOT_SKIP_SCAN_PREFIXES,
    CASE_DIR_WAL_ISOLATION,
    CASE_FILE_NOTESTORE_SHM,
    CASE_FILE_NOTESTORE_SQLITE,
    CASE_FILE_NOTESTORE_WAL,
    case_dir,
    matches_any_case_prefix,
    matches_case_prefix,
)
from notes_recovery.models import HitSource
from notes_recovery.io import iter_files_safe


def should_skip_recovery_path(path: Path) -> bool:
    for part in path.parts:
        if matches_any_case_prefix(part, CASE_ROOT_SKIP_SCAN_PREFIXES):
            return True
    return False


def collect_deep_scan_targets(root_dir: Path) -> list[Path]:
    targets: list[Path] = []

    db_dir = case_dir(root_dir, CASE_DIR_DB_BACKUP)
    recovered_db_dir = case_dir(root_dir, CASE_DIR_RECOVERED_DB)
    cache_dir = case_dir(root_dir, CASE_DIR_CACHE_BACKUP)
    spotlight_dir = case_dir(root_dir, CASE_DIR_SPOTLIGHT_BACKUP)

    for name in (CASE_FILE_NOTESTORE_SQLITE, CASE_FILE_NOTESTORE_WAL, CASE_FILE_NOTESTORE_SHM):
        path = db_dir / name
        if path.exists():
            targets.append(path)

    wal_isolation = case_dir(db_dir, CASE_DIR_WAL_ISOLATION)
    if wal_isolation.exists():
        targets.extend(sorted(wal_isolation.glob("*.sqlite-wal")))
        targets.extend(sorted(wal_isolation.glob("*.sqlite-shm")))

    if recovered_db_dir.exists():
        targets.extend([p for p in sorted(recovered_db_dir.glob("*.sqlite")) if not p.is_symlink()])

    for name in ("NotesV7.storedata", "NotesV7.storedata-wal", "NotesV7.storedata-shm"):
        path = cache_dir / name
        if path.exists() and not path.is_symlink():
            targets.append(path)

    if spotlight_dir.exists():
        targets.extend([p for p in sorted(spotlight_dir.rglob("store.db")) if not p.is_symlink()])
        targets.extend([p for p in sorted(spotlight_dir.rglob(".store.db")) if not p.is_symlink()])
        for txt_file in spotlight_dir.rglob("*.txt"):
            if not txt_file.is_symlink():
                targets.append(txt_file)

    return targets


def collect_deep_scan_targets_extended(root_dir: Path) -> list[Path]:
    targets = set(collect_deep_scan_targets(root_dir))
    for base in (
        case_dir(root_dir, CASE_DIR_DB_BACKUP),
        case_dir(root_dir, CASE_DIR_CACHE_BACKUP),
        case_dir(root_dir, CASE_DIR_SPOTLIGHT_BACKUP),
        case_dir(root_dir, CASE_DIR_RECOVERED_DB),
    ):
        if not base.exists():
            continue
        for path in iter_files_safe(base):
            if should_skip_recovery_path(path):
                continue
            targets.add(path)
    return sorted(targets)


def collect_prefixed_dirs(root_dir: Path, prefix: str) -> list[Path]:
    dirs: list[Path] = []
    if not root_dir.exists():
        return dirs
    for path in sorted(root_dir.iterdir()):
        if path.is_dir() and matches_case_prefix(path.name, prefix):
            dirs.append(path)
    return dirs


def classify_binary_target(path: Path) -> tuple[HitSource, float, str]:
    name = path.name.lower()
    if "notestore.sqlite" in name:
        return HitSource.BINARY, 1.3, "NoteStore"
    if "notestore.sqlite-wal" in name or "notestore.sqlite-shm" in name:
        return HitSource.BINARY, 1.2, "NoteStore_WAL"
    if "notesv7.storedata" in name:
        return HitSource.BINARY, 1.1, "NotesCache"
    if name in {"store.db", ".store.db"}:
        return HitSource.BINARY, 0.9, "Spotlight"
    if path.suffix in {".txt", ".json", ".plist"}:
        return HitSource.BINARY, 1.0, "TextCache"
    return HitSource.BINARY, 1.0, "Binary"
