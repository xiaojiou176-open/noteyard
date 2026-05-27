from __future__ import annotations

import argparse
import json
from pathlib import Path

import notes_recovery.config as config
from notes_recovery.core import pipeline
from notes_recovery.models import StageResult, StageStatus


def test_pipeline_hash_and_manifest(tmp_path: Path, monkeypatch) -> None:
    db_dir = tmp_path / "DB_Backup"
    db_dir.mkdir()
    db_path = db_dir / "NoteStore.sqlite"
    db_path.write_text("db", encoding="utf-8")
    wal_path = db_dir / "NoteStore.sqlite-wal"
    wal_path.write_text("wal", encoding="utf-8")

    targets = pipeline.collect_snapshot_hash_targets(tmp_path)
    assert db_path in targets
    assert wal_path in targets

    run_ts = "20260101_000000"
    manifest = pipeline.write_hash_manifest(tmp_path, run_ts, targets, "snapshot")
    assert manifest and manifest.exists()
    content = manifest.read_text(encoding="utf-8")
    assert "sha256" in content

    # HMAC signing path
    monkeypatch.setattr(config, "CASE_SIGN_MODE", "hmac")
    monkeypatch.setattr(config, "CASE_HMAC_KEY", "secret")
    sigs = pipeline.maybe_sign_file(manifest)
    assert sigs
    assert manifest.with_suffix(manifest.suffix + ".hmac").exists()


def test_pipeline_timestamp_and_command_utils(tmp_path: Path) -> None:
    argv = ["notes-recovery", "snapshot", "--dir", "case one"]
    payload = pipeline.build_command_line(argv)
    assert payload["argv"] == argv
    assert "snapshot" in payload["command"]

    base_dir = tmp_path / "Case"
    ts = "20260101_000000"
    base_dir.mkdir(parents=True)
    timestamped_dir = pipeline.build_timestamped_dir(base_dir, ts)
    assert timestamped_dir.name.startswith("Case_20260101_000000")

    path = tmp_path / "file.txt"
    path.write_text("x", encoding="utf-8")
    unique = pipeline.ensure_unique_file(path)
    assert unique != path

    file_ts = pipeline.build_timestamped_file(path, ts)
    assert file_ts.stem.startswith("file_20260101_000000")


def test_sign_file_pgp_failure(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "target.txt"
    target.write_text("data", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise RuntimeError("pgp fail")

    monkeypatch.setattr(pipeline.subprocess, "run", boom)
    sig = pipeline.sign_file_pgp(target, key="KEY", homedir="", binary="gpg")
    assert sig is None


def test_sign_file_pgp_success_with_homedir(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "target.txt"
    target.write_text("data", encoding="utf-8")

    def ok(*_args, **_kwargs):
        return None

    monkeypatch.setattr(pipeline.subprocess, "run", ok)
    sig = pipeline.sign_file_pgp(target, key="KEY", homedir="/tmp", binary="gpg")
    assert sig and sig.suffix == ".asc"


def test_sign_file_hmac_branches(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "target.txt"
    target.write_text("data", encoding="utf-8")

    assert pipeline.sign_file_hmac(target, "") is None

    def boom(*_args, **_kwargs):
        raise RuntimeError("hmac fail")

    monkeypatch.setattr(pipeline, "compute_hmac_sha256", boom)
    assert pipeline.sign_file_hmac(target, "secret") is None


def test_pipeline_run_manifest(tmp_path: Path) -> None:
    run_ts = "20260101_000000"
    result = StageResult(
        name="snapshot",
        required=True,
        enabled=True,
        status=StageStatus.OK,
        started_at="t0",
        ended_at="t1",
        duration_ms=1,
        error=None,
        outputs={"path": "ok"},
        skip_reason=None,
    )
    manifest = pipeline.write_run_manifest(
        root_dir=tmp_path,
        run_ts=run_ts,
        mode="auto",
        config_payload={"run": True},
        stage_results=[result],
        extra={"note": "x"},
    )
    assert manifest.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["mode"] == "auto"
    assert data["stages"][0]["name"] == "snapshot"


def test_configure_case_manifest(monkeypatch) -> None:
    args = argparse.Namespace(
        case_no_manifest=False,
        case_sign="hmac",
        case_hmac_key="",
        case_pgp_key="",
        case_pgp_homedir="",
        case_pgp_binary="gpg",
    )
    monkeypatch.setenv("NOTES_CASE_HMAC_KEY", "")
    pipeline.configure_case_manifest(args)
    assert config.CASE_SIGN_MODE == "none"


def test_configure_case_manifest_pgp_missing_key(monkeypatch) -> None:
    args = argparse.Namespace(
        case_no_manifest=False,
        case_sign="pgp",
        case_hmac_key="",
        case_pgp_key="",
        case_pgp_homedir="",
        case_pgp_binary="gpg",
    )
    pipeline.configure_case_manifest(args)
    assert config.CASE_SIGN_MODE == "none"


def test_pipeline_collectors_and_paths(tmp_path: Path) -> None:
    run_ts = "20260101_000000"
    root = tmp_path / "root"
    root.mkdir()

    manifest = root / f"snapshot_hashes_{run_ts}.csv"
    manifest.write_text("path,bytes,sha256\n", encoding="utf-8")
    sidecar = root / f"snapshot_hashes_{run_ts}.csv.hmac"
    sidecar.write_text("sig", encoding="utf-8")

    manifests = pipeline.collect_hash_manifests(root, run_ts)
    assert str(manifest) in manifests

    sidecars = pipeline.collect_signature_sidecars(root, run_ts)
    assert str(sidecar) in sidecars

    nested = {"a": [manifest, {"b": str(manifest)}], "c": "missing"}
    paths = pipeline.extract_paths_from_outputs(nested)
    assert str(manifest) in paths
    assert pipeline.extract_paths_from_outputs(123) == []

    assert pipeline.write_hash_manifest(root, run_ts, [], "empty") is None


def test_write_case_manifest_and_finalize(tmp_path: Path, monkeypatch) -> None:
    run_ts = "20260101_000000"
    root = tmp_path / "root"
    root.mkdir()
    sample = root / "sample.txt"
    sample.write_text("x", encoding="utf-8")

    result = StageResult(
        name="snapshot",
        required=True,
        enabled=True,
        status=StageStatus.OK,
        started_at="t0",
        ended_at="t1",
        duration_ms=1,
        error=None,
        outputs={"path": str(sample)},
        skip_reason=None,
    )

    monkeypatch.setattr(config, "CASE_MANIFEST_ENABLED", True)
    monkeypatch.setattr(config, "CASE_SIGN_MODE", "hmac")
    monkeypatch.setattr(config, "CASE_HMAC_KEY", "secret")

    run_manifest = pipeline.write_run_manifest(root, run_ts, "auto", {"k": "v"}, [result])
    case_path = pipeline.write_case_manifest(root, run_ts, run_manifest, None, {"k": "v"}, [result])
    assert case_path and case_path.exists()

    missing_root = tmp_path / "missing"
    manifest, summary = pipeline.finalize_pipeline(missing_root, run_ts, "auto", {"k": "v"}, [result])
    assert manifest is None and summary is None


def test_assert_pipeline_ok_raises() -> None:
    failed = StageResult(
        name="stage",
        required=True,
        enabled=True,
        status=StageStatus.FAILED,
        started_at="t0",
        ended_at="t1",
        duration_ms=1,
        error="boom",
        outputs={},
        skip_reason=None,
    )
    try:
        pipeline.assert_pipeline_ok([failed])
    except RuntimeError:
        assert True
