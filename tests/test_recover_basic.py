from pathlib import Path

from notes_recovery.services import recover
from notes_recovery.core.keywords import build_variants_for_keywords
from notes_recovery.models import FragmentSource


def test_recover_helpers() -> None:
    label = recover.sanitize_label("a/b\\c")
    assert "__" in label

    variants = build_variants_for_keywords(["hello"])
    frag = recover.build_fragment(
        "hello world",
        FragmentSource.TEXT,
        "source",
        Path("file.txt"),
        variants,
        match_all=False,
        truncated=False,
    )
    assert frag is not None
    assert recover.score_hit(3, 100) > 0


def test_recover_notes_by_keyword(tmp_path: Path) -> None:
    root = tmp_path / "Notes_Forensics"
    query_dir = root / "Query_Output"
    blob_dir = root / "Recovered_Blobs"
    query_dir.mkdir(parents=True)
    blob_dir.mkdir(parents=True)
    (query_dir / "sample.csv").write_text("a,b\nhello,world\n", encoding="utf-8")
    (blob_dir / "blob_0001.txt").write_text("hello world", encoding="utf-8")

    out_dir = root / "Recovered_Notes"
    recover.recover_notes_by_keyword(
        root_dir=root,
        keyword="hello",
        out_dir=out_dir,
        min_overlap=10,
        max_fragments=50,
        max_stitch_rounds=50,
        include_deep=False,
        deep_all=False,
        deep_max_mb=0,
        deep_max_hits_per_file=50,
        match_all=False,
        binary_copy=False,
        binary_copy_max_mb=0,
        run_ts="20260101_000000",
    )
    assert out_dir.exists()
