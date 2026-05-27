# -*- coding: utf-8 -*-
"""Filesystem and validation helpers."""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import Iterable


def resolve_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def is_within(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def ensure_dir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise RuntimeError(f"Failed to create directory: {path} -> {exc}")


def ensure_safe_output_dir(out_dir: Path, sources: list[Path], label: str) -> None:
    out_dir = out_dir.expanduser().resolve()
    if out_dir.exists() and out_dir.is_file():
        raise RuntimeError(f"{label} output path points to a file: {out_dir}")
    for src in sources:
        src = src.expanduser().resolve()
        if out_dir == src:
            raise RuntimeError(f"{label} output directory must not match a source directory: {out_dir}")
        if is_within(out_dir, src):
            raise RuntimeError(f"{label} output directory must not live inside a source directory: {out_dir}")
        if is_within(src, out_dir):
            raise RuntimeError(f"{label} output directory must not contain a source directory: {out_dir}")


def iter_files_safe(base: Path) -> Iterable[Path]:
    base = base.expanduser().resolve()
    for root, dirs, files in os.walk(base, topdown=True, followlinks=False):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if not (root_path / d).is_symlink()]
        dirs.sort()
        files.sort()
        for name in files:
            path = root_path / name
            if path.is_symlink():
                continue
            yield path


def safe_stat_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except Exception:
        return 0


def require_positive_int(value: int, label: str) -> int:
    if value <= 0:
        raise RuntimeError(f"{label} must be a positive integer: {value}")
    return value


def require_non_negative_int(value: int, label: str) -> int:
    if value < 0:
        raise RuntimeError(f"{label} must not be negative: {value}")
    return value


def require_float_range(value: float, label: str, minimum: float, maximum: float) -> float:
    if value < minimum or value > maximum:
        raise RuntimeError(f"{label} must stay between {minimum} and {maximum}: {value}")
    return value


def require_non_negative_float(value: float, label: str) -> float:
    if value < 0:
        raise RuntimeError(f"{label} must not be negative: {value}")
    return value


def hash_file(path: Path, algo: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.new(algo)
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_hmac_sha256(path: Path, key: str, chunk_size: int = 1024 * 1024) -> str:
    h = hmac.new(key.encode("utf-8"), digestmod=hashlib.sha256)
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_read_text(path: Path, max_chars: int) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            if max_chars <= 0:
                return f.read()
            remaining = max_chars
            chunks: list[str] = []
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            return "".join(chunks)
    except Exception:
        return ""


def read_text_limited(path: Path, max_chars: int) -> tuple[str, bool]:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            if max_chars <= 0:
                return f.read(), False
            remaining = max_chars + 1
            chunks: list[str] = []
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            text = "".join(chunks)
    except Exception:
        return "", False
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars], True
    return text, False
