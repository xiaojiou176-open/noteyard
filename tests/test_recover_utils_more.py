from __future__ import annotations

import types
from pathlib import Path

import notes_recovery.services.recover as recover
from notes_recovery.services import recover_sqlite as recover_sqlite_impl
from notes_recovery.models import BinaryHit, FragmentSource, SearchVariant, StitchNode, TextFragment


def test_recover_string_utils() -> None:
    assert recover.sanitize_label("a/b") == "a__b"
    assert recover.strip_urls("http://example.com abc") == "abc"
    assert recover.overlap_size("hello world", "world!!!", min_len=3, max_scan=10) >= 5
    assert recover.is_trivial_overlap("http://example.com", min_non_url_chars=3)

    signature = recover.build_text_signature("hello world")
    assert signature
    bucket = recover.signature_bucket(signature, len("hello world"))
    assert bucket
    ratio = recover.jaccard_signature(signature, signature)
    assert ratio == 1.0

    frag = TextFragment(
        text="hello world",
        source=FragmentSource.TEXT,
        source_detail="src",
        file="file",
        occurrences=1,
        keyword_hits=1,
        length=11,
        truncated=False,
        stitchable=True,
        score=1.0,
    )
    clusters = recover.cluster_fragments_by_signature([(0, frag)])
    assert clusters

    node = StitchNode(text="hello world", fragment_ids=[0], sources={"TEXT"}, cluster_id=1, merge_count=1, overlap_total=5)
    confidence = recover.compute_stitch_confidence(node)
    assert 0.0 < confidence <= 1.0

    deduped = recover.dedupe_stitch_candidates([frag, frag])
    assert len(deduped) == 1

def test_sqlite_recover_and_binary_outputs(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "db.sqlite"
    db_path.write_text("db", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(recover, "get_sqlite3_path", lambda: Path("/usr/bin/sqlite3"))

    def fake_run(*_args, **_kwargs):
        return types.SimpleNamespace(stderr="")

    monkeypatch.setattr(recover.subprocess, "run", fake_run)
    recovered_db = recover.sqlite_recover(db_path, out_dir, ignore_freelist=False, lost_and_found="")
    assert recovered_db.name.endswith("_recovered.sqlite")

    bin_path = tmp_path / "bin.dat"
    bin_path.write_bytes(b"xxxxsecretxxxx")
    hits = [BinaryHit(bin_path, [4], 1.0, "db")]
    recover.write_binary_hits_outputs(
        out_dir,
        hits,
        keyword="secret",
        run_ts="20260101_000000",
        preview_bytes=64,
        max_chars=200,
        max_copy_mb=1,
        raw_slice_bytes=64,
    )
    assert list(out_dir.glob("binary_hits_*.csv"))


def test_get_sqlite3_path_branches(monkeypatch) -> None:
    original_exists = recover_sqlite_impl.Path.exists

    def fake_exists(self: Path) -> bool:
        if str(self) == "/usr/bin/sqlite3":
            return False
        return original_exists(self)

    monkeypatch.setattr(recover_sqlite_impl.Path, "exists", fake_exists, raising=False)
    monkeypatch.setattr(recover_sqlite_impl.shutil, "which", lambda _name: "/usr/local/bin/sqlite3")
    path = recover.get_sqlite3_path()
    assert path.name == "sqlite3"

    monkeypatch.setattr(recover_sqlite_impl.shutil, "which", lambda _name: None)
    try:
        recover.get_sqlite3_path()
    except RuntimeError:
        assert True


def test_evaluate_and_build_fragment_match_all() -> None:
    variants_map = {
        "a": [SearchVariant("a", 1.0, "exact")],
        "b": [SearchVariant("b", 1.0, "exact")],
    }
    total, hits, weighted = recover.evaluate_text_hits("a only", variants_map, match_all=True)
    assert total == 0
    assert hits == 1
    assert weighted == 0.0

    frag = recover.build_fragment(
        text="no hit",
        source=FragmentSource.TEXT,
        source_detail="detail",
        file_path=Path("file.txt"),
        variants_map=variants_map,
        match_all=False,
        truncated=False,
    )
    assert frag is None
