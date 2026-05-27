# -*- coding: utf-8 -*-
"""Text utilities shared by recovery engines."""

from __future__ import annotations

import html
import re
from pathlib import Path


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_loose(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).strip()


def extract_urls(text: str) -> list[str]:
    if not text:
        return []
    return re.findall(r"https?://[^\s\"'>]+", text)


def html_to_text(raw: str) -> str:
    if not raw:
        return ""
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", raw)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def strip_html_tags(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", text).strip()


def infer_title_from_text(path: Path, text: str) -> str:
    if not text:
        return path.stem
    if path.suffix.lower() in {".md", ".markdown"}:
        for line in text.splitlines()[:6]:
            if line.startswith("#"):
                return line.lstrip("#").strip()[:200] or path.stem
    return path.stem
