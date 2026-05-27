from __future__ import annotations

from pathlib import Path

from notes_recovery.models import SearchVariant, FragmentSource, TextFragment, StitchNode
from notes_recovery.services import recover


def test_overlap_and_signature_helpers() -> None:
    assert recover.overlap_size("abc123", "123xyz", min_len=2, max_scan=10) == 3
    assert recover.overlap_size("", "x", min_len=1, max_scan=10) == 0
    assert recover.is_trivial_overlap("http://example.com", min_non_url_chars=3) is True

    signature = recover.build_text_signature("!!!")
    assert signature
    bucket = recover.signature_bucket([], text_len=1200)
    assert bucket.startswith("len_")
    assert recover.jaccard_signature([], [1, 2]) == 0.0


def test_cluster_and_confidence() -> None:
    frag = TextFragment(
        text="hello world",
        source=FragmentSource.BLOB,
        source_detail="x",
        file="f",
        occurrences=1,
        keyword_hits=1,
        length=11,
        truncated=False,
        stitchable=True,
        score=1.0,
    )
    clusters = recover.cluster_fragments_by_signature([(1, frag), (2, frag)])
    assert clusters
    node = StitchNode(text="hello", fragment_ids=[1], sources={"blob"}, cluster_id=1, merge_count=1, overlap_total=3)
    assert recover.compute_stitch_confidence(node) > 0


def test_write_text_outputs(tmp_path: Path) -> None:
    text = "hello"
    md = tmp_path / "out.md"
    html = tmp_path / "out.html"
    txt = tmp_path / "out.txt"
    recover.write_text_content_markdown(text, md, "Title", ["meta"], truncated=False)
    recover.write_text_content_html(text, html, "Title", ["meta"], truncated=False)
    recover.write_text_content_txt(text, txt)
    assert md.exists() and html.exists() and txt.exists()


def test_binary_pattern_and_scan(tmp_path: Path) -> None:
    variant = SearchVariant("secret", 1.0, "exact")
    patterns = recover.build_variant_binary_patterns(variant, min_utf16_len=3)
    assert patterns

    binary = tmp_path / "data.bin"
    binary.write_bytes(b"secret" + "secret".encode("utf-16le"))
    occ, weight, preview = recover.scan_binary_for_variants(
        binary,
        [variant],
        preview_len=64,
        max_hits_per_file=10,
        max_file_bytes=1024 * 1024,
    )
    assert occ > 0
    assert weight > 0.0
    assert preview

    offsets, weights = recover.scan_binary_for_variants_offsets(
        binary,
        [variant],
        max_hits_per_file=5,
        max_file_bytes=1024 * 1024,
    )
    assert offsets
    assert weights

    assert recover.read_binary_preview(binary, offset=0, preview_bytes=0) == ""
    assert recover.score_hit(occurrences=1.0, length=0) == 0.0
