from __future__ import annotations

from notes_recovery.core import keywords


def test_split_and_keyword_match() -> None:
    items = keywords.split_keywords("alpha, beta，gamma|delta")
    assert items == ["alpha", "beta", "gamma", "delta"]
    assert keywords.keyword_matches_any("Hello Beta", items) is True
    assert keywords.keyword_matches_any("", items) is False
    assert keywords.keyword_matches_any("text", []) is False


def test_count_occurrences_variants_and_fuzzy() -> None:
    assert keywords.count_occurrences("abc abc", "abc") == 2
    assert keywords.count_occurrences("abc", "") == 0
    assert keywords.count_occurrences_for_keywords("a b c", ["a", "c"]) == 2
    assert keywords.count_occurrences_for_keywords("a b c", []) == 0

    variants = keywords.build_search_variants("https://example.com/a?b=1#frag")
    total, weighted = keywords.count_occurrences_variants("https://example.com/a?b=1#frag", variants)
    assert total > 0
    assert weighted > 0

    ratio = keywords.fuzzy_ratio("hello world", "hello", max_len=50)
    assert 0 < ratio <= 1.0


def test_build_variants_for_keywords_and_preview() -> None:
    variants_map = keywords.build_variants_for_keywords(["Alpha", "Beta"])
    assert "Alpha" in variants_map
    preview = keywords.choose_best_text_preview(["bad\x00\x00", "good text"])
    assert "good" in preview
    assert keywords.build_search_variants("") == []


def test_keywords_url_tokens_and_file_counts(tmp_path) -> None:
    keyword = "Visit https://example.com/path?x=1 ... and www.example.com/"
    variants = keywords.build_search_variants(keyword)
    assert any(v.label == "url" for v in variants)
    assert any(v.label == "token" for v in variants)
    assert any(v.label == "url_host" for v in variants)
    assert any(v.label == "url_no_query" for v in variants)

    data_path = tmp_path / "data.txt"
    data_path.write_text("example.com/path?x=1\n", encoding="utf-8")
    occ, length, weighted = keywords.count_occurrences_variants_in_file(data_path, variants)
    assert length > 0
    assert weighted >= 0.0
