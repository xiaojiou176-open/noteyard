from __future__ import annotations

from notes_recovery.core.keywords import choose_best_text_preview_with_label
from notes_recovery.utils.bytes import is_printable_char


def extract_strings_from_bytes(data: bytes, min_len: int, max_chars: int) -> str:
    if not data or max_chars <= 0:
        return ""
    chunks = []
    current: list[str] = []
    count = 0
    for b in data:
        ch = chr(b)
        if is_printable_char(ch):
            current.append(ch)
        else:
            if len(current) >= min_len:
                text = "".join(current)
                chunks.append(text)
                count += len(text) + 1
                if count >= max_chars:
                    break
            current = []
        if count >= max_chars:
            break
    if len(current) >= min_len and count < max_chars:
        chunks.append("".join(current))
    return "\n".join(chunks)[:max_chars]


def decode_carved_payload(data: bytes, max_chars: int) -> tuple[str, str]:
    if not data or max_chars <= 0:
        return "", ""
    candidates = [
        ("utf-8", data.decode("utf-8", errors="ignore")),
        ("utf-16le", data.decode("utf-16le", errors="ignore")),
        ("utf-16be", data.decode("utf-16be", errors="ignore")),
    ]
    best, label = choose_best_text_preview_with_label(candidates)
    if best:
        return best[:max_chars], label
    ascii_text = extract_strings_from_bytes(data, 4, max_chars)
    if ascii_text:
        return ascii_text, "ascii_strings"
    return "", ""
