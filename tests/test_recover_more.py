from __future__ import annotations

from pathlib import Path

from notes_recovery.core.keywords import build_variants_for_keywords, split_keywords
from notes_recovery.models import FragmentSource, SearchVariant, TextFragment
import notes_recovery.services.recover as recover


def _prepare_root(root: Path) -> None:
    (root / "Recovered_Blobs").mkdir(parents=True)
    (root / "Plugins_Output" / "toolA").mkdir(parents=True)
    (root / "Query_Output").mkdir(parents=True)
    (root / "Recovered_Notes").mkdir(parents=True)


def test_collect_fragments_and_outputs(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _prepare_root(root)

    keyword = "secret"
    variants_map = build_variants_for_keywords(split_keywords(keyword))

    blob_path = root / "Recovered_Blobs" / "blob.txt"
    blob_path.write_text("secret blob text", encoding="utf-8")

    plugin_path = root / "Plugins_Output" / "toolA" / "plugin.log"
    plugin_path.write_text("secret plugin", encoding="utf-8")

    csv_path = root / "Query_Output" / "notes.csv"
    csv_path.write_text("title,body\nsecret,hello\n", encoding="utf-8")

    cache_dir = root / "Cache_Backup"
    cache_dir.mkdir(parents=True, exist_ok=True)
    text_path = cache_dir / "note.txt"
    text_path.write_text("secret in text file", encoding="utf-8")

    blobs = recover.collect_fragments_from_blobs(root, variants_map, match_all=False, max_chars=200, max_items=10)
    plugins = recover.collect_fragments_from_plugins(root, variants_map, match_all=False, max_chars=200, max_items=10)
    csvs = recover.collect_fragments_from_csv(root, variants_map, match_all=False, max_rows=10)
    texts = recover.collect_fragments_from_text_files(
        root,
        variants_map,
        match_all=False,
        max_chars=200,
        max_files=10,
        max_file_mb=1,
    )

    assert blobs
    assert plugins
    assert csvs
    assert texts

    out_dir = tmp_path / "out"
    run_ts = "20260101_000000"
    manifest = recover.write_fragments_outputs(out_dir, blobs[:1], keyword, run_ts)
    assert manifest.exists()


def test_stitch_and_binary_scan(tmp_path: Path) -> None:
    fragments = [
        TextFragment(
            text="alpha secret beta",
            source=FragmentSource.TEXT,
            source_detail="a",
            file="a",
            occurrences=1,
            keyword_hits=1,
            length=18,
            truncated=False,
            stitchable=True,
            score=1.0,
        ),
        TextFragment(
            text="beta gamma secret",
            source=FragmentSource.TEXT,
            source_detail="b",
            file="b",
            occurrences=1,
            keyword_hits=1,
            length=17,
            truncated=False,
            stitchable=True,
            score=1.0,
        ),
    ]
    nodes = recover.stitch_fragments(fragments, min_overlap=3, max_scan=50, min_non_url_chars=3, max_rounds=3)
    assert nodes

    variants_map = build_variants_for_keywords(["secret"])
    out_dir = tmp_path / "stitched"
    run_ts = "20260101_000000"
    stitched_manifest = recover.write_stitched_outputs(out_dir, nodes, "secret", run_ts, variants_map)
    assert stitched_manifest.exists()

    binary_path = tmp_path / "bin.dat"
    binary_path.write_bytes(b"xxxxsecretxxxx")
    variants = [SearchVariant("secret", 1.0, "exact")]
    occ, weighted, preview = recover.scan_binary_for_variants(
        binary_path,
        variants,
        preview_len=20,
        max_hits_per_file=10,
        max_file_bytes=10 * 1024,
    )
    assert occ >= 1
    assert weighted >= 1.0
    assert "secret" in preview

    offsets, weights = recover.scan_binary_for_variants_offsets(
        binary_path,
        variants,
        max_hits_per_file=10,
        max_file_bytes=10 * 1024,
    )
    assert offsets
    assert weights


def test_recover_notes_by_keyword_minimal(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _prepare_root(root)
    (root / "Recovered_Blobs" / "blob.txt").write_text("secret blob", encoding="utf-8")
    out_dir = tmp_path / "recover"

    recover.recover_notes_by_keyword(
        root_dir=root,
        keyword="secret",
        out_dir=out_dir,
        min_overlap=3,
        max_fragments=10,
        max_stitch_rounds=2,
        include_deep=False,
        deep_all=False,
        deep_max_mb=1,
        deep_max_hits_per_file=10,
        match_all=False,
        binary_copy=False,
        binary_copy_max_mb=1,
        run_ts="20260101_000000",
    )

    manifests = list(out_dir.rglob("*manifest_*.csv"))
    assert manifests
