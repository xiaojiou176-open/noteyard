# -*- coding: utf-8 -*-
"""Binary/text decoding helpers."""

from __future__ import annotations

from pathlib import Path


def is_printable_char(ch: str) -> bool:
    if not ch:
        return False
    if ch == "\x00":
        return False
    return ch.isprintable()


def read_binary_window(path: Path, offset: int, window_bytes: int) -> bytes:
    try:
        file_size = path.stat().st_size
    except Exception:
        return b""
    if file_size <= 0:
        return b""
    half = max(1, window_bytes // 2)
    start = max(0, offset - half)
    if start > file_size:
        start = max(0, file_size - window_bytes)
    try:
        with path.open("rb") as f:
            f.seek(start)
            return f.read(window_bytes)
    except Exception:
        return b""


def hex_dump(data: bytes, width: int = 16) -> str:
    if not data:
        return ""
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        text_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:08x}  {hex_part:<{width * 3}}  {text_part}")
    return "\n".join(lines)


def extract_printable_sequences(text: str, min_len: int, carry: str) -> tuple[list[str], str]:
    if min_len <= 0:
        min_len = 1
    results: list[str] = []
    current = list(carry) if carry else []
    for ch in text:
        if is_printable_char(ch):
            current.append(ch)
        else:
            if len(current) >= min_len:
                results.append("".join(current))
            current = []
    return results, "".join(current)


def merge_text_sections(sections: list[tuple[str, str]], max_chars: int) -> str:
    if max_chars <= 0 or not sections:
        return ""
    remaining = max_chars
    out: list[str] = []
    total_sections = len(sections)
    for idx, (label, text) in enumerate(sections):
        if not text:
            continue
        header = f"[{label}]\n"
        quota = max(1, remaining // max(1, total_sections - idx))
        chunk = (header + text)[:quota]
        out.append(chunk)
        remaining -= len(chunk)
        if remaining <= 0:
            break
    return "\n\n".join(out)[:max_chars]


def extract_utf16_strings(
    path: Path,
    encoding: str,
    min_len: int,
    max_chars: int,
    chunk_size: int,
) -> str:
    del chunk_size
    if max_chars <= 0:
        return ""
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    strings: list[str] = []
    total_chars = 0
    for start in (0, 1):
        current: list[str] = []
        saw_ascii = False
        for idx in range(start, max(0, len(data) - 1), 2):
            pair = data[idx:idx + 2]
            if len(pair) < 2:
                break
            try:
                ch = pair.decode(encoding, errors="ignore")
            except Exception:
                ch = ""
            if len(ch) == 1 and is_printable_char(ch):
                current.append(ch)
                saw_ascii = saw_ascii or ch.isascii()
                continue
            if saw_ascii and len(current) >= min_len:
                s = "".join(current)
                strings.append(s)
                total_chars += len(s) + 1
                if total_chars >= max_chars:
                    return "\n".join(strings)[:max_chars]
            current = []
            saw_ascii = False
        if saw_ascii and len(current) >= min_len and total_chars < max_chars:
            s = "".join(current)
            strings.append(s)
            total_chars += len(s) + 1
            if total_chars >= max_chars:
                return "\n".join(strings)[:max_chars]
    return "\n".join(strings)[:max_chars]


def extract_printable_strings(
    path: Path,
    min_len: int,
    max_chars: int,
    chunk_size: int = 1024 * 1024,
) -> str:
    if max_chars <= 0:
        return ""
    strings: list[str] = []
    current: list[str] = []
    total_chars = 0
    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                for b in chunk:
                    if 32 <= b < 127:
                        current.append(chr(b))
                    else:
                        if len(current) >= min_len:
                            s = "".join(current)
                            strings.append(s)
                            total_chars += len(s) + 1
                            if total_chars >= max_chars:
                                return "\n".join(strings)[:max_chars]
                        current = []
                if total_chars >= max_chars:
                    break
        if len(current) >= min_len and total_chars < max_chars:
            s = "".join(current)
            strings.append(s)
    except Exception:
        return ""
    ascii_text = "\n".join(strings)[:max_chars]
    utf16_le_text = extract_utf16_strings(path, "utf-16le", min_len, max_chars, chunk_size)
    utf16_be_text = extract_utf16_strings(path, "utf-16be", min_len, max_chars, chunk_size)
    sections = []
    if ascii_text:
        sections.append(("ASCII", ascii_text))
    if utf16_le_text:
        sections.append(("UTF-16LE", utf16_le_text))
    if utf16_be_text:
        sections.append(("UTF-16BE", utf16_be_text))
    if not sections:
        return ""
    return merge_text_sections(sections, max_chars)
