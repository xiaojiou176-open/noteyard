from __future__ import annotations

from pathlib import Path

from notes_recovery.core.keywords import build_variants_for_keywords
from notes_recovery.models import FragmentSource, SearchVariant, TextFragment
import notes_recovery.services.recover as recover


def test_sanitize_label_and_overlap() -> None:
    assert recover.sanitize_label("") == "unknown"
    cleaned = recover.sanitize_label("a/b\\c")
    assert "__" in cleaned

    stripped = recover.strip_urls("see https://example.com ok")
    assert stripped == "seeok"

    assert recover.overlap_size("abc", "cde", min_len=0, max_scan=10) == 1
    assert recover.overlap_size("abc", "xyz", min_len=1, max_scan=10) == 0


def test_build_variant_binary_patterns_utf16() -> None:
    variant = SearchVariant("secret", 1.0, "exact")
    patterns = recover.build_variant_binary_patterns(variant, min_utf16_len=3)
    assert any(pat == b"secret" for pat in patterns)
    assert any(len(pat) > len(b"secret") for pat in patterns)


def test_signature_cluster_and_confidence() -> None:
    frag1 = TextFragment(
        text="alpha beta secret",
        source=FragmentSource.TEXT,
        source_detail="a",
        file="a",
        occurrences=1,
        keyword_hits=1,
        length=18,
        truncated=False,
        stitchable=True,
        score=1.0,
    )
    frag2 = TextFragment(
        text="beta secret gamma",
        source=FragmentSource.TEXT,
        source_detail="b",
        file="b",
        occurrences=1,
        keyword_hits=1,
        length=17,
        truncated=False,
        stitchable=True,
        score=1.0,
    )
    sig1 = recover.build_text_signature(frag1.text)
    sig2 = recover.build_text_signature(frag2.text)
    assert sig1 and sig2
    assert recover.signature_bucket(sig1, len(frag1.text))
    assert recover.jaccard_signature(sig1, sig2) >= 0.0

    clusters = recover.cluster_fragments_by_signature([(0, frag1), (1, frag2)])
    assert clusters


def test_collect_fragments_from_deep_and_binary_outputs(tmp_path: Path) -> None:
    root = tmp_path / "root"
    db_dir = root / "DB_Backup"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "NoteStore.sqlite"
    db_path.write_bytes(b"xxxxsecret-data-xxxx")

    variants_map = build_variants_for_keywords(["secret"])
    fragments, hits = recover.collect_fragments_from_deep(
        root_dir=root,
        variants_map=variants_map,
        preview_len=32,
        max_hits_per_file=10,
        max_file_mb=1,
        max_files=10,
        deep_all=False,
    )
    assert hits
    assert fragments

    out_dir = tmp_path / "binary"
    recover.write_binary_hits_outputs(
        out_dir=out_dir,
        hits=hits,
        keyword="secret",
        run_ts="20260101_000000",
        preview_bytes=64,
        max_chars=200,
        max_copy_mb=1,
        raw_slice_bytes=16,
    )

    manifests = list(out_dir.glob("binary_hits_*.csv"))
    assert manifests


def test_read_binary_preview_edge(tmp_path: Path) -> None:
    path = tmp_path / "data.bin"
    path.write_bytes(b"abcdsecret")
    assert recover.read_binary_preview(path, offset=0, preview_bytes=0) == ""
    preview = recover.read_binary_preview(path, offset=1000, preview_bytes=8)
    assert "secret" in preview or preview


def test_sqlite_recover_happy_path(tmp_path: Path, monkeypatch) -> None:
    import sqlite3

    db_path = tmp_path / "notes.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()

    class _FakeCompleted:
        def __init__(self) -> None:
            self.stderr = ""

    def _fake_run(*_args, **kwargs):
        stdout = kwargs.get("stdout")
        if stdout is not None and hasattr(stdout, "write"):
            stdout.write("CREATE TABLE t (id INTEGER);")
        return _FakeCompleted()

    monkeypatch.setattr(recover, "get_sqlite3_path", lambda: Path("/usr/bin/sqlite3"))
    monkeypatch.setattr(recover.subprocess, "run", _fake_run)

    out_dir = tmp_path / "out"
    out_db = recover.sqlite_recover(db_path, out_dir, ignore_freelist=False, lost_and_found="")
    assert out_db.name.endswith("_recovered.sqlite")


def test_stitch_fragments_merge_direction_ba() -> None:
    frag_a = TextFragment(
        text="gamma|alpha|beta",
        source=FragmentSource.TEXT,
        source_detail="a",
        file="a",
        occurrences=1,
        keyword_hits=1,
        length=17,
        truncated=False,
        stitchable=True,
        score=1.0,
    )
    frag_b = TextFragment(
        text="alpha-beta-gamma",
        source=FragmentSource.TEXT,
        source_detail="b",
        file="b",
        occurrences=1,
        keyword_hits=1,
        length=17,
        truncated=False,
        stitchable=True,
        score=1.0,
    )
    nodes = recover.stitch_fragments([frag_a, frag_b], min_overlap=5, max_scan=20, min_non_url_chars=3, max_rounds=2)
    assert len(nodes) == 1


def test_recover_notes_by_keyword_with_deep(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "Recovered_Blobs").mkdir(parents=True)
    (root / "Plugins_Output").mkdir(parents=True)
    (root / "Query_Output").mkdir(parents=True)
    (root / "Cache_Backup").mkdir(parents=True)
    (root / "Recovered_Notes").mkdir(parents=True)

    (root / "Recovered_Blobs" / "blob.txt").write_text("secret blob", encoding="utf-8")
    (root / "Cache_Backup" / "NotesV7.storedata").write_bytes(b"secret cache")

    db_dir = root / "DB_Backup"
    db_dir.mkdir()
    (db_dir / "NoteStore.sqlite").write_bytes(b"secret db content")

    out_dir = tmp_path / "recover"
    recover.recover_notes_by_keyword(
        root_dir=root,
        keyword="secret",
        out_dir=out_dir,
        min_overlap=3,
        max_fragments=10,
        max_stitch_rounds=2,
        include_deep=True,
        deep_all=False,
        deep_max_mb=1,
        deep_max_hits_per_file=10,
        match_all=False,
        binary_copy=True,
        binary_copy_max_mb=1,
        run_ts="20260101_000000",
    )

    assert list(out_dir.rglob("fragments_manifest_*.csv"))
    assert list(out_dir.rglob("binary_hits_*.csv"))


def test_recover_binary_limits_and_sidecars(tmp_path: Path) -> None:
    data_path = tmp_path / "big.bin"
    data_path.write_bytes(b"x" * 10)
    variants = [SearchVariant("x", 1.0, "exact")]

    occ, weighted, preview = recover.scan_binary_for_variants(
        data_path,
        variants,
        preview_len=10,
        max_hits_per_file=5,
        max_file_bytes=1,
    )
    assert occ == 0
    assert weighted == 0.0
    assert preview == ""

    offsets, weights = recover.scan_binary_for_variants_offsets(
        data_path,
        variants,
        max_hits_per_file=5,
        max_file_bytes=1,
    )
    assert offsets == []
    assert weights == {}

    base = tmp_path / "note.md"
    base.write_text("x", encoding="utf-8")
    sidecars = recover.collect_sidecar_paths(base)
    assert base in sidecars

    md_path = tmp_path / "out.md"
    recover.write_text_content_markdown("text", md_path, "title", ["meta"], truncated=True)
    assert md_path.exists()


def _make_fragment(text: str, detail: str) -> TextFragment:
    return TextFragment(
        text=text,
        source=FragmentSource.TEXT,
        source_detail=detail,
        file=detail,
        occurrences=1,
        keyword_hits=1,
        length=len(text),
        truncated=False,
        stitchable=True,
        score=1.0,
    )


def test_stitch_fragments_overlap_branches() -> None:
    frag_a = _make_fragment("alpha", "a")
    frag_b = _make_fragment("beta", "b")
    nodes = recover.stitch_fragments([frag_a, frag_b], min_overlap=10, max_scan=50, min_non_url_chars=3, max_rounds=1)
    assert len(nodes) == 2

    url = "http://example.com"
    frag_c = _make_fragment(url, "c")
    frag_d = _make_fragment(url, "d")
    nodes = recover.stitch_fragments([frag_c, frag_d], min_overlap=5, max_scan=200, min_non_url_chars=3, max_rounds=1)
    assert len(nodes) == 2

    frag_e = _make_fragment("alpha-beta-gamma", "e")
    frag_f = _make_fragment("gamma-delta-alpha", "f")
    nodes = recover.stitch_fragments([frag_e, frag_f], min_overlap=5, max_scan=50, min_non_url_chars=3, max_rounds=2)
    assert len(nodes) == 1


def test_evaluate_text_hits_and_build_fragment() -> None:
    variants_map = build_variants_for_keywords(["alpha", "beta"])
    total, hits, weighted = recover.evaluate_text_hits("alpha only", variants_map, match_all=True)
    assert total == 0
    assert weighted == 0.0

    fragment = recover.build_fragment(
        text="alpha beta",
        source=FragmentSource.TEXT,
        source_detail="detail",
        file_path=Path("file.txt"),
        variants_map=variants_map,
        match_all=False,
        truncated=False,
    )
    assert fragment is not None

    assert recover.build_fragment(
        text="",
        source=FragmentSource.TEXT,
        source_detail="detail",
        file_path=Path("file.txt"),
        variants_map=variants_map,
        match_all=False,
        truncated=False,
    ) is None
