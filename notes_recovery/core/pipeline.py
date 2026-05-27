from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import os
import platform
import re
import sqlite3
import subprocess
import shlex
import sys
import time
from pathlib import Path
from typing import Any, Optional

import notes_recovery.config as config
from notes_recovery.case_contract import (
    CASE_DIR_DB_BACKUP,
    CASE_DIR_META,
    CASE_DIR_WAL_ISOLATION,
    CASE_FILE_NOTESTORE_SHM,
    CASE_FILE_NOTESTORE_SQLITE,
    CASE_FILE_NOTESTORE_WAL,
    case_dir,
    case_manifest_path,
    pipeline_summary_path,
    run_manifest_path,
)
from notes_recovery.io import compute_hmac_sha256, ensure_dir, hash_file, safe_stat_size
from notes_recovery.logging import eprint, log_warn
from notes_recovery.models import PipelineStage, StageResult, StageStatus
from notes_recovery.services.review_index import generate_review_index

ABSOLUTE_PATH_PATTERN = re.compile(
    "|".join(
        (
            re.escape("/" + "Users" + "/"),
            re.escape("/" + "home" + "/"),
            r"[A-Za-z]:\\" + "Users" + r"\\",
        )
    )
)
REDACTED_CASE_ROOT = "<case-root>"
REDACTED_VALUE = "<redacted>"


def build_command_line(argv: list[str]) -> dict[str, Any]:
    quoted = " ".join(shlex.quote(item) for item in argv)
    return {"argv": argv, "command": quoted}


def sign_file_hmac(path: Path, key: str) -> Optional[Path]:
    if not key:
        return None
    try:
        digest = compute_hmac_sha256(path, key)
        out_path = path.with_suffix(path.suffix + ".hmac")
        with out_path.open("w", encoding="utf-8") as f:
            f.write(digest)
        return out_path
    except Exception as exc:
        log_warn(f"HMAC signing failed: {path} -> {exc}")
        return None


def sign_file_pgp(path: Path, key: str, homedir: str, binary: str) -> Optional[Path]:
    if not key:
        return None
    out_path = path.with_suffix(path.suffix + ".asc")
    cmd = [binary, "--batch", "--yes", "--armor", "--detach-sign", "--local-user", key, "--output", str(out_path), str(path)]
    if homedir:
        cmd = [binary, "--homedir", homedir] + cmd[1:]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return out_path
    except Exception as exc:
        log_warn(f"PGP signing failed: {path} -> {exc}")
        return None


def maybe_sign_file(path: Path) -> list[dict[str, Any]]:
    signatures: list[dict[str, Any]] = []
    if config.CASE_SIGN_MODE == "hmac" and config.CASE_HMAC_KEY:
        hmac_path = sign_file_hmac(path, config.CASE_HMAC_KEY)
        if hmac_path:
            key_fp = hashlib.sha256(config.CASE_HMAC_KEY.encode("utf-8")).hexdigest()[:12]
            signatures.append({"type": "hmac-sha256", "path": str(hmac_path), "key_fingerprint": key_fp})
    elif config.CASE_SIGN_MODE == "pgp" and config.CASE_PGP_KEY:
        sig_path = sign_file_pgp(path, config.CASE_PGP_KEY, config.CASE_PGP_HOMEDIR, config.CASE_PGP_BINARY)
        if sig_path:
            signatures.append({"type": "pgp", "path": str(sig_path), "key_id": config.CASE_PGP_KEY})
    return signatures


def write_hash_manifest(out_dir: Path, run_ts: str, targets: list[Path], label: str) -> Optional[Path]:
    if not targets:
        return None
    ensure_dir(out_dir)
    manifest_path = out_dir / f"{label}_hashes_{run_ts}.csv"
    try:
        with manifest_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["path", "bytes", "sha256"])
            for target in targets:
                if not target.exists() or target.is_symlink() or not target.is_file():
                    continue
                size = safe_stat_size(target)
                digest = hash_file(target)
                writer.writerow([str(target), size, digest])
    except Exception as exc:
        eprint(f"Failed to write hash manifest: {manifest_path} -> {exc}")
        return None
    if config.CASE_SIGN_MODE != "none":
        maybe_sign_file(manifest_path)
    return manifest_path


def collect_snapshot_hash_targets(out_dir: Path) -> list[Path]:
    targets: list[Path] = []
    db_dir = case_dir(out_dir, CASE_DIR_DB_BACKUP)
    for name in (CASE_FILE_NOTESTORE_SQLITE, CASE_FILE_NOTESTORE_WAL, CASE_FILE_NOTESTORE_SHM):
        path = db_dir / name
        if path.exists() and not path.is_symlink():
            targets.append(path)
    wal_isolation = case_dir(db_dir, CASE_DIR_WAL_ISOLATION)
    if wal_isolation.exists():
        targets.extend([p for p in sorted(wal_isolation.glob("*.sqlite-wal")) if not p.is_symlink()])
        targets.extend([p for p in sorted(wal_isolation.glob("*.sqlite-shm")) if not p.is_symlink()])
    return targets


def timestamp_now() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def build_timestamped_dir(base: Path, ts: str, suffix: str = "") -> Path:
    name = f"{base.name}_{ts}{suffix}"
    candidate = base.parent / name
    counter = 1
    while candidate.exists():
        candidate = base.parent / f"{base.name}_{ts}{suffix}_{counter}"
        counter += 1
    return candidate


def build_timestamped_file(path: Path, ts: str) -> Path:
    base_name = f"{path.stem}_{ts}{path.suffix}"
    candidate = path.with_name(base_name)
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_{ts}_{counter}{path.suffix}")
        counter += 1
    return candidate


def ensure_unique_file(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def collect_runtime_fingerprint() -> dict[str, str]:
    sqlite_python = sqlite3.sqlite_version
    return {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "sqlite_version": sqlite3.sqlite_version,
        "sqlite_python": sqlite_python,
        "platform": platform.platform(),
        "hostname": platform.node(),
        "machine": platform.machine(),
        "processor": platform.processor() or "",
        "cwd": str(Path.cwd()),
        "timezone": "/".join(time.tzname) if time.tzname else "",
    }


def sanitize_public_safe_string(value: str, case_root: Path) -> str:
    if not value:
        return value
    case_root_str = str(case_root.resolve())
    normalized = value.replace(case_root_str, REDACTED_CASE_ROOT)
    if ABSOLUTE_PATH_PATTERN.search(normalized):
        return REDACTED_VALUE
    return normalized


def redact_public_safe_payload(value: Any, case_root: Path) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            if key in {"hostname", "cwd", "python_executable", "machine", "processor", "timezone"}:
                continue
            if key == "root_dir":
                redacted[key] = REDACTED_CASE_ROOT
                continue
            if key == "command_line":
                redacted[key] = {"argv": [REDACTED_VALUE], "command": REDACTED_VALUE}
                continue
            redacted[key] = redact_public_safe_payload(child, case_root)
        return redacted
    if isinstance(value, list):
        return [redact_public_safe_payload(item, case_root) for item in value]
    if isinstance(value, tuple):
        return [redact_public_safe_payload(item, case_root) for item in value]
    if isinstance(value, set):
        return [redact_public_safe_payload(item, case_root) for item in sorted(value, key=str)]
    if isinstance(value, str):
        return sanitize_public_safe_string(value, case_root)
    return value


def configure_case_manifest(args: argparse.Namespace) -> None:
    config.CASE_MANIFEST_ENABLED = not getattr(args, "case_no_manifest", False)
    config.CASE_SIGN_MODE = getattr(args, "case_sign", "none")
    config.CASE_HMAC_KEY = getattr(args, "case_hmac_key", "") or os.environ.get("NOTES_CASE_HMAC_KEY", "")
    config.CASE_PGP_KEY = getattr(args, "case_pgp_key", "") or os.environ.get("NOTES_CASE_PGP_KEY", "")
    config.CASE_PGP_HOMEDIR = getattr(args, "case_pgp_homedir", "") or os.environ.get("NOTES_CASE_PGP_HOME", "")
    config.CASE_PGP_BINARY = getattr(args, "case_pgp_binary", "gpg") or "gpg"

    if config.CASE_SIGN_MODE == "hmac" and not config.CASE_HMAC_KEY:
        log_warn("case-manifest signing mode is hmac, but no key was provided; falling back to none.")
        config.CASE_SIGN_MODE = "none"
    if config.CASE_SIGN_MODE == "pgp" and not config.CASE_PGP_KEY:
        log_warn("case-manifest signing mode is pgp, but no key was provided; falling back to none.")
        config.CASE_SIGN_MODE = "none"


def stage_result_to_dict(result: StageResult) -> dict[str, Any]:
    return {
        "name": result.name,
        "required": result.required,
        "enabled": result.enabled,
        "status": result.status.value,
        "started_at": result.started_at,
        "ended_at": result.ended_at,
        "duration_ms": result.duration_ms,
        "error": result.error,
        "outputs": result.outputs,
        "skip_reason": result.skip_reason,
    }


def write_run_manifest(
    root_dir: Path,
    run_ts: str,
    mode: str,
    config_payload: dict[str, Any],
    stage_results: list[StageResult],
    extra: Optional[dict[str, Any]] = None,
) -> Path:
    ensure_dir(root_dir)
    manifest_path = run_manifest_path(root_dir, run_ts)
    payload = {
        "mode": mode,
        "run_ts": run_ts,
        "root_dir": str(root_dir),
        "generated_at": now_iso(),
        "runtime": collect_runtime_fingerprint(),
        "command_line": build_command_line(sys.argv),
        "config": config_payload,
        "stages": [stage_result_to_dict(s) for s in stage_results],
    }
    if extra:
        payload["extra"] = extra
    try:
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to write run manifest: {manifest_path} -> {exc}")
    if config.CASE_SIGN_MODE != "none":
        maybe_sign_file(manifest_path)
    return manifest_path


def extract_paths_from_outputs(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            paths.extend(extract_paths_from_outputs(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            paths.extend(extract_paths_from_outputs(item))
    else:
        try:
            if isinstance(value, Path):
                candidate = value
            elif isinstance(value, str) and value:
                candidate = Path(value)
            else:
                return paths
            if candidate.exists():
                paths.append(str(candidate))
        except Exception:
            return paths
    return paths


def collect_hash_manifests(root_dir: Path, run_ts: str) -> list[str]:
    manifests: list[str] = []
    pattern = f"*hashes_{run_ts}.csv"
    for path in root_dir.rglob(pattern):
        if path.is_file():
            manifests.append(str(path))
    return sorted(set(manifests))


def collect_signature_sidecars(root_dir: Path, run_ts: str) -> list[str]:
    files: list[str] = []
    for suffix in (".hmac", ".asc"):
        for path in root_dir.rglob(f"*{run_ts}*{suffix}"):
            if path.is_file():
                files.append(str(path))
    return sorted(set(files))


def write_case_manifest(
    root_dir: Path,
    run_ts: str,
    run_manifest: Path,
    summary_path: Optional[Path],
    config_payload: dict[str, Any],
    stage_results: list[StageResult],
) -> Optional[Path]:
    if not config.CASE_MANIFEST_ENABLED:
        return None
    case_path = case_manifest_path(root_dir, run_ts)
    outputs: list[str] = []
    for stage in stage_results:
        outputs.extend(extract_paths_from_outputs(stage.outputs))
    payload = {
        "case_id": run_ts,
        "generated_at": now_iso(),
        "root_dir": str(root_dir),
        "runtime": collect_runtime_fingerprint(),
        "command_line": build_command_line(sys.argv),
        "config": config_payload,
        "run_manifest": str(run_manifest),
        "pipeline_summary": str(summary_path) if summary_path else "",
        "hash_manifests": collect_hash_manifests(root_dir, run_ts),
        "stage_outputs": sorted(set(outputs)),
        "signature_sidecars": collect_signature_sidecars(root_dir, run_ts),
    }
    try:
        with case_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2)
    except Exception as exc:
        log_warn(f"Failed to write case manifest: {case_path} -> {exc}")
        return None
    signatures = maybe_sign_file(case_path) if config.CASE_SIGN_MODE != "none" else []
    if signatures:
        payload["signatures"] = signatures
        try:
            with case_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=True, indent=2)
        except Exception as exc:
            log_warn(f"Failed to update case manifest signatures: {case_path} -> {exc}")
    return case_path


def run_pipeline(stages: list[PipelineStage]) -> list[StageResult]:
    results: list[StageResult] = []
    for stage in stages:
        started_at = now_iso()
        start_time = time.time()
        if not stage.enabled:
            results.append(
                StageResult(
                    name=stage.name,
                    required=stage.required,
                    enabled=stage.enabled,
                    status=StageStatus.SKIPPED,
                    started_at=started_at,
                    ended_at=now_iso(),
                    duration_ms=0,
                    error=None,
                    outputs={},
                    skip_reason="disabled",
                )
            )
            continue
        try:
            outputs = stage.action() or {}
            ended_at = now_iso()
            results.append(
                StageResult(
                    name=stage.name,
                    required=stage.required,
                    enabled=stage.enabled,
                    status=StageStatus.OK,
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error=None,
                    outputs=outputs,
                )
            )
        except Exception as exc:
            ended_at = now_iso()
            results.append(
                StageResult(
                    name=stage.name,
                    required=stage.required,
                    enabled=stage.enabled,
                    status=StageStatus.FAILED,
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error=str(exc),
                    outputs={},
                )
            )
            if stage.required:
                break
    return results


def write_pipeline_summary(
    root_dir: Path,
    run_ts: str,
    mode: str,
    stage_results: list[StageResult],
    config_payload: Optional[dict[str, Any]] = None,
) -> Path:
    meta_dir = case_dir(root_dir, CASE_DIR_META)
    ensure_dir(meta_dir)
    summary_path = pipeline_summary_path(root_dir, run_ts)
    ok_count = sum(1 for s in stage_results if s.status == StageStatus.OK)
    failed_count = sum(1 for s in stage_results if s.status == StageStatus.FAILED)
    skipped_count = sum(1 for s in stage_results if s.status == StageStatus.SKIPPED)

    def short(text: Optional[str], max_len: int = 140) -> str:
        if not text:
            return ""
        compact = " ".join(text.split())
        if len(compact) <= max_len:
            return compact
        return compact[:max_len - 3] + "..."

    try:
        with summary_path.open("w", encoding="utf-8") as f:
            f.write("# Pipeline Summary\n\n")
            f.write(f"- Mode: {mode}\n")
            f.write(f"- Run timestamp: {run_ts}\n")
            f.write(f"- Generated at: {now_iso()}\n")
            f.write(f"- Stage totals: OK {ok_count} | FAILED {failed_count} | SKIPPED {skipped_count}\n\n")
            f.write("| Stage | Required | Enabled | Status | Duration (ms) | Notes |\n")
            f.write("| --- | --- | --- | --- | --- | --- |\n")
            for stage in stage_results:
                note = stage.skip_reason or short(stage.error)
                f.write(
                    f"| {stage.name} | {'Y' if stage.required else 'N'} | "
                    f"{'Y' if stage.enabled else 'N'} | {stage.status.value} | {stage.duration_ms} | {note} |\n"
                )
            if config_payload:
                f.write("\n## Configuration\n\n")
                for key, value in config_payload.items():
                    f.write(f"- {key}: {value}\n")
    except Exception as exc:
        log_warn(f"Failed to write pipeline summary: {summary_path} -> {exc}")
    return summary_path


def finalize_pipeline(
    root_dir: Path,
    run_ts: str,
    mode: str,
    config_payload: dict[str, Any],
    stage_results: list[StageResult],
) -> tuple[Optional[Path], Optional[Path]]:
    if not root_dir.exists():
        eprint(f"Output directory was not created; skipping run manifest and summary: {root_dir}")
        return None, None
    manifest_path = None
    summary_path = None
    try:
        manifest_path = write_run_manifest(root_dir, run_ts, mode, config_payload, stage_results)
        summary_path = write_pipeline_summary(root_dir, run_ts, mode, stage_results, config_payload)
        print(f"Run manifest: {manifest_path}")
        print(f"Pipeline summary: {summary_path}")
        case_path = write_case_manifest(root_dir, run_ts, manifest_path, summary_path, config_payload, stage_results)
        if case_path:
            print(f"Case manifest: {case_path}")
        review_index_path = generate_review_index(root_dir, run_ts, mode, stage_results)
        print(f"Review index: {review_index_path}")
    except Exception as exc:
        eprint(f"Failed to write run manifest, pipeline summary, case manifest, or review index: {exc}")
    return manifest_path, summary_path


def assert_pipeline_ok(stage_results: list[StageResult]) -> None:
    for stage in stage_results:
        if stage.required and stage.status == StageStatus.FAILED:
            raise RuntimeError(f"Required stage failed: {stage.name} -> {stage.error}")
