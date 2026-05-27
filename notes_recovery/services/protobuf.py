from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Iterable, Optional

from notes_recovery.config import (
    GZIP_MAGIC,
    ICLOUD_PROFILE_SPEC,
    PROTOBUF_ATTACHMENT_MAX_ITEMS,
    PROTOBUF_ATTR_RUN_MAX_CANDIDATES,
    PROTOBUF_EMBEDDED_TYPES,
    PROTOBUF_FORMAT_HINT_KEYS,
    PROTOBUF_NOTE_TEXT_MAX_CANDIDATES,
    PROTOBUF_NOTE_TEXT_MIN_LEN,
    PROTOBUF_URL_MAX_ITEMS,
    PROTOBUF_UUID_REGEX,
    PROTOBUF_UTI_PREFIXES,
)
from notes_recovery.core.pipeline import ensure_unique_file
from notes_recovery.core.sqlite_utils import (
    build_query_profile,
    detect_schema,
    escape_like,
    open_sqlite_readonly,
    profile_columns,
    table_columns,
)
from notes_recovery.io import ensure_dir
from notes_recovery.logging import eprint
from notes_recovery.models import SchemaType
from notes_recovery.services.recover import sanitize_label
from notes_recovery.utils.bytes import is_printable_char
from notes_recovery.utils.text import extract_urls


def load_blackboxprotobuf():
    try:
        import blackboxprotobuf
        return blackboxprotobuf
    except Exception as exc:
        raise RuntimeError(
            "Missing blackboxprotobuf. Install it first with: pip install blackboxprotobuf"
        ) from exc


def maybe_decompress_zdata(blob: bytes, max_output_bytes: int) -> tuple[bytes, bool]:
    if not blob:
        return b"", False
    if blob[:3] != GZIP_MAGIC:
        return blob, False
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(blob)) as gz:
            data = gz.read(max_output_bytes + 1)
        if len(data) > max_output_bytes:
            raise RuntimeError("ZDATA expanded past the configured limit. Possible compression bomb.")
        return data, True
    except Exception as exc:
        raise RuntimeError(f"Failed to decompress ZDATA gzip payload: {exc}")


def decode_protobuf_message(data: bytes) -> tuple[dict, dict]:
    bb = load_blackboxprotobuf()
    message_obj = {}
    typedef = {}
    try:
        message_obj, typedef = bb.decode_message(data)
    except Exception:
        msg_json, typedef = bb.protobuf_to_json(data)
        if isinstance(msg_json, str):
            try:
                message_obj = json.loads(msg_json)
            except Exception:
                message_obj = {"raw_json": msg_json}
        else:
            message_obj = msg_json

    try:
        from blackboxprotobuf.lib.output import json_safe_transform, sort_output, sort_typedef
        message_obj = json_safe_transform(message_obj, typedef)
        message_obj = sort_output(message_obj, typedef)
        typedef = sort_typedef(typedef)
    except Exception:
        pass
    return message_obj, typedef


def json_safe_value(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, memoryview)):
        data = bytes(value)
        preview = data[:48]
        payload: dict[str, Any] = {
            "__bytes__": {
                "len": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "preview_hex": preview.hex(),
            }
        }
        text, encoding = decode_bytes_candidate(data)
        if text:
            payload["__bytes__"]["preview_text"] = text[:2000]
            payload["__bytes__"]["encoding_hint"] = encoding
        return payload
    if isinstance(value, dict):
        return {str(key): json_safe_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [json_safe_value(child) for child in value]
    if isinstance(value, tuple):
        return [json_safe_value(child) for child in value]
    return value


def walk_obj(value: Any, path: str = "root") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_obj(child, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            yield from walk_obj(child, f"{path}[{idx}]")


def extract_embedded_objects(message: Any) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for path, value in walk_obj(message):
        if isinstance(value, str):
            lower = value.lower()
            for token in PROTOBUF_EMBEDDED_TYPES:
                if token in lower:
                    results.append({"path": path, "type": token, "value": value})
    return results


def extract_formatting_hints(message: Any) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for path, value in walk_obj(message):
        if isinstance(value, str):
            lower = value.lower()
            if any(k in lower for k in PROTOBUF_FORMAT_HINT_KEYS):
                results.append({"path": path, "hint": value})
        if isinstance(value, dict):
            for key in value.keys():
                key_lower = str(key).lower()
                if any(k in key_lower for k in PROTOBUF_FORMAT_HINT_KEYS):
                    results.append({"path": path, "hint": str(key)})
    return results


def is_probable_uuid(text: str) -> bool:
    if not text:
        return False
    return bool(PROTOBUF_UUID_REGEX.search(text))


def is_probable_uti(text: str) -> bool:
    lower = text.lower()
    return any(lower.startswith(prefix) for prefix in PROTOBUF_UTI_PREFIXES)


def text_printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for ch in text if is_printable_char(ch) or ch in "\n\r\t")
    return printable / max(1, len(text))


def score_text_candidate(text: str) -> float:
    if not text:
        return 0.0
    length = len(text)
    ratio = text_printable_ratio(text)
    url_count = len(extract_urls(text))
    whitespace_ratio = sum(1 for ch in text if ch.isspace()) / max(1, length)
    penalty = 0.0
    if is_probable_uuid(text):
        penalty += 120.0
    if is_probable_uti(text):
        penalty += 80.0
    if length < PROTOBUF_NOTE_TEXT_MIN_LEN:
        penalty += 200.0
    return length + ratio * 180.0 + url_count * 25.0 + whitespace_ratio * 80.0 - penalty


def decode_bytes_candidate(data: bytes) -> tuple[str, str]:
    best_text = ""
    best_encoding = ""
    best_score = 0.0
    for encoding in ("utf-8", "utf-16le", "utf-16be"):
        try:
            text = data.decode(encoding, errors="ignore")
        except Exception:
            continue
        text = text.strip()
        if not text or len(text) < PROTOBUF_NOTE_TEXT_MIN_LEN:
            continue
        if text_printable_ratio(text) < 0.6:
            continue
        score = score_text_candidate(text)
        if score > best_score:
            best_text = text
            best_encoding = encoding
            best_score = score
    return best_text, best_encoding


def extract_note_text_candidates(message: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path, value in walk_obj(message):
        text = ""
        encoding_hint = ""
        if isinstance(value, str):
            text = value.strip()
        elif isinstance(value, (bytes, bytearray, memoryview)):
            text, encoding_hint = decode_bytes_candidate(bytes(value))
        else:
            continue
        if not text:
            continue
        if len(text) < PROTOBUF_NOTE_TEXT_MIN_LEN:
            continue
        digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        score = score_text_candidate(text)
        path_hint = path.lower()
        if path_hint.endswith(".2") or ".2[" in path_hint:
            score += 60.0
        candidates.append(
            {
                "path": path if not encoding_hint else f"{path}#bytes:{encoding_hint}",
                "text": text,
                "length": len(text),
                "urls": len(extract_urls(text)),
                "printable_ratio": round(text_printable_ratio(text), 4),
                "score": round(score, 2),
            }
        )
    candidates.sort(key=lambda x: (x["score"], x["length"]), reverse=True)
    return candidates[:PROTOBUF_NOTE_TEXT_MAX_CANDIDATES]


def select_best_note_text(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return ""
    return candidates[0]["text"]


def looks_like_attribute_run(item: dict[str, Any]) -> bool:
    int_fields = sum(1 for v in item.values() if isinstance(v, int))
    str_fields = sum(1 for v in item.values() if isinstance(v, str))
    list_fields = sum(1 for v in item.values() if isinstance(v, list))
    return int_fields >= 2 and (str_fields >= 1 or list_fields >= 1)


def extract_attribute_run_candidates(message: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for path, value in walk_obj(message):
        if not isinstance(value, list) or not value:
            continue
        if not all(isinstance(item, dict) for item in value):
            continue
        matched = [item for item in value if looks_like_attribute_run(item)]
        if not matched:
            continue
        ratio = len(matched) / max(1, len(value))
        if ratio < 0.6:
            continue
        candidates.append(
            {
                "path": path,
                "total_runs": len(value),
                "matched_runs": len(matched),
                "sample": matched[:3],
            }
        )
    def sort_key(item: dict[str, Any]) -> tuple[int, int]:
        path_hint = str(item.get("path", "")).lower()
        path_bonus = 1 if path_hint.endswith(".5") or ".5[" in path_hint else 0
        return (item.get("total_runs", 0), path_bonus)
    candidates.sort(key=sort_key, reverse=True)
    return candidates[:PROTOBUF_ATTR_RUN_MAX_CANDIDATES]


def collect_urls_from_message(message: Any) -> list[str]:
    urls = []
    for _path, value in walk_obj(message):
        if isinstance(value, str) and value.startswith("http"):
            urls.extend(extract_urls(value))
        if len(urls) >= PROTOBUF_URL_MAX_ITEMS:
            break
    return urls[:PROTOBUF_URL_MAX_ITEMS]


def extract_uuid_tokens(message: Any) -> list[str]:
    tokens: list[str] = []
    for _path, value in walk_obj(message):
        if not isinstance(value, str):
            continue
        if is_probable_uuid(value):
            tokens.append(value)
            if len(tokens) >= PROTOBUF_ATTACHMENT_MAX_ITEMS:
                break
    return tokens[:PROTOBUF_ATTACHMENT_MAX_ITEMS]


def extract_uti_tokens(message: Any) -> list[str]:
    tokens: list[str] = []
    for _path, value in walk_obj(message):
        if not isinstance(value, str):
            continue
        if is_probable_uti(value):
            tokens.append(value)
            if len(tokens) >= PROTOBUF_ATTACHMENT_MAX_ITEMS:
                break
    return tokens[:PROTOBUF_ATTACHMENT_MAX_ITEMS]


def fetch_attachment_candidates(conn, note_id: int, object_columns: set[str]) -> list[dict[str, Any]]:
    if "ZATTACHMENT" not in object_columns:
        return []
    sql = (
        "SELECT ZIDENTIFIER, ZTITLE1, ZTYPEUTI, ZFILENAME, ZURLSTRING, ZCONTAINER, ZNOTE "
        "FROM ZICCLOUDSYNCINGOBJECT WHERE ZATTACHMENT=1 AND ZNOTE=?"
    )
    try:
        rows = conn.execute(sql, (note_id,)).fetchall()
    except Exception:
        return []
    results = []
    for row in rows:
        results.append({
            "ZIDENTIFIER": row[0],
            "ZTITLE1": row[1],
            "ZTYPEUTI": row[2],
            "ZFILENAME": row[3],
            "ZURLSTRING": row[4],
            "ZCONTAINER": row[5],
            "ZNOTE": row[6],
        })
    return results


def tag_attachment_candidates(
    attachments: list[dict[str, Any]],
    uti_tokens: list[str],
    uuid_tokens: list[str],
) -> list[dict[str, Any]]:
    tagged: list[dict[str, Any]] = []
    for item in attachments:
        tags = []
        for token in uti_tokens:
            if token and token in str(item.get("ZTYPEUTI", "")):
                tags.append("uti_match")
        for token in uuid_tokens:
            if token and token in str(item.get("ZIDENTIFIER", "")):
                tags.append("uuid_match")
        if tags:
            item["match_tags"] = tags
        tagged.append(item)
    return tagged


def write_structured_note_markdown(
    out_path: Path,
    note_id: int,
    identifier: str,
    title: str,
    snippet: str,
    note_text: str,
    urls: list[str],
    attribute_runs: list[dict[str, Any]],
    attachments: list[dict[str, Any]],
) -> None:
    ensure_dir(out_path.parent)
    try:
        with out_path.open("w", encoding="utf-8") as f:
            f.write("# Notes Protobuf Structured Recovery\n\n")
            f.write(f"- NoteID: {note_id}\n")
            if identifier:
                f.write(f"- Identifier: {identifier}\n")
            if title:
                f.write(f"- Title: {title}\n")
            if snippet:
                f.write(f"- Snippet: {snippet}\n")
            f.write("\n## Parsed Text (Best-Effort)\n\n")
            if note_text:
                f.write("```text\n")
                f.write(note_text)
                if not note_text.endswith("\n"):
                    f.write("\n")
                f.write("```\n")
            else:
                f.write("No clear note body text was recovered.\n")
            f.write("\n## URLs\n\n")
            if urls:
                for url in urls:
                    f.write(f"- {url}\n")
            else:
                f.write("No URLs were found.\n")
            f.write("\n## Attribute Runs (Candidate)\n\n")
            if attribute_runs:
                for item in attribute_runs:
                    f.write(f"- Path: {item.get('path','')} | Runs: {item.get('total_runs',0)}\n")
            else:
                f.write("No obvious Attribute Run list was found.\n")
            f.write("\n## Attachments (Candidate)\n\n")
            if attachments:
                for item in attachments:
                    ident = item.get("ZIDENTIFIER", "")
                    uti = item.get("ZTYPEUTI", "")
                    url = item.get("ZURLSTRING", "")
                    title1 = item.get("ZTITLE1", "")
                    filename = item.get("ZFILENAME", "")
                    tags = ",".join(item.get("match_tags", [])) if isinstance(item, dict) else ""
                    f.write(f"- id={ident} uti={uti} title={title1} file={filename} url={url} tags={tags}\n")
            else:
                f.write("No attachment candidates were found.\n")
    except Exception as exc:
        eprint(f"Failed to write protobuf markdown: {out_path} -> {exc}")


def parse_notes_protobuf(
    db_path: Path,
    out_dir: Path,
    keyword: Optional[str],
    max_notes: int,
    max_zdata_mb: int,
    run_ts: str,
) -> Path:
    ensure_dir(out_dir)
    conn = open_sqlite_readonly(db_path)
    try:
        schema = detect_schema(conn)
        if schema != SchemaType.ICLOUD:
            raise RuntimeError("Protobuf parsing currently supports only the iCloud schema (ZICNOTEDATA).")
        profile = build_query_profile(conn, ICLOUD_PROFILE_SPEC)
        object_all_cols = table_columns(conn, "ZICCLOUDSYNCINGOBJECT")
        object_cols = profile_columns(profile, "ZICCLOUDSYNCINGOBJECT", ["Z_PK", "ZIDENTIFIER", "ZTITLE1", "ZSNIPPET", "ZNOTEDATA"])
        note_cols = profile_columns(profile, "ZICNOTEDATA", ["Z_PK", "ZDATA"])
        if "ZNOTEDATA" not in object_cols or "ZDATA" not in note_cols:
            raise RuntimeError("ZICNOTEDATA.ZDATA is unavailable, so protobuf parsing cannot continue.")

        max_bytes = max_zdata_mb * 1024 * 1024 if max_zdata_mb > 0 else 0
        notes_dir = out_dir / "Notes"
        ensure_dir(notes_dir)
        manifest_path = ensure_unique_file(out_dir / f"protobuf_manifest_{run_ts}.csv")

        where = ["d.ZDATA IS NOT NULL"]
        params: list[Any] = []
        if keyword and "ZTITLE1" in object_cols and "ZSNIPPET" in object_cols:
            escaped = escape_like(keyword)
            where.append("(o.ZTITLE1 LIKE ? ESCAPE '\\' OR o.ZSNIPPET LIKE ? ESCAPE '\\')")
            params.extend([f"%{escaped}%", f"%{escaped}%"])
        where_clause = " AND ".join(where)

        sql = (
            "SELECT o.Z_PK, o.ZIDENTIFIER, o.ZTITLE1, o.ZSNIPPET, d.ZDATA "
            "FROM ZICCLOUDSYNCINGOBJECT o "
            "LEFT JOIN ZICNOTEDATA d ON d.Z_PK = o.ZNOTEDATA "
            f"WHERE {where_clause} "
            "ORDER BY o.Z_PK DESC LIMIT ?"
        )
        params.append(max_notes)

        rows = conn.execute(sql, tuple(params)).fetchall()
        results: list[list[Any]] = []
        for idx, row in enumerate(rows, start=1):
            note_id = row[0]
            identifier = row[1] or ""
            title = row[2] or ""
            snippet = row[3] or ""
            zdata = row[4]
            if zdata is None:
                continue
            if isinstance(zdata, memoryview):
                zdata_bytes = zdata.tobytes()
            else:
                zdata_bytes = bytes(zdata)
            raw_size = len(zdata_bytes)
            if max_bytes > 0 and raw_size > max_bytes:
                results.append([
                    note_id,
                    identifier,
                    title,
                    raw_size,
                    False,
                    "",
                    "",
                    "skip",
                    "zdata_too_large",
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    snippet,
                ])
                continue
            gzip_used = False
            parse_error = ""
            embedded_count = 0
            format_count = 0
            note_text_len = 0
            url_count = 0
            attachment_count = 0
            attr_run_count = 0
            out_path = ""
            md_path = ""
            try:
                payload, gzip_used = maybe_decompress_zdata(zdata_bytes, max_bytes or raw_size)
                message_obj, typedef = decode_protobuf_message(payload)
                embedded_objects = extract_embedded_objects(message_obj)
                formatting_hints = extract_formatting_hints(message_obj)
                embedded_count = len(embedded_objects)
                format_count = len(formatting_hints)
                text_candidates = extract_note_text_candidates(message_obj)
                best_text = select_best_note_text(text_candidates)
                note_text_len = len(best_text)
                urls = extract_urls(best_text)
                extra_urls = collect_urls_from_message(message_obj)
                for url in extra_urls:
                    if url not in urls:
                        urls.append(url)
                    if len(urls) >= PROTOBUF_URL_MAX_ITEMS:
                        break
                url_count = len(urls)
                attribute_runs = extract_attribute_run_candidates(message_obj)
                attr_run_count = sum(item.get("total_runs", 0) for item in attribute_runs)
                uuid_tokens = extract_uuid_tokens(message_obj)
                uti_tokens = extract_uti_tokens(message_obj)
                attachments = fetch_attachment_candidates(conn, note_id, object_all_cols)
                attachments = tag_attachment_candidates(attachments, uti_tokens, uuid_tokens)
                attachment_count = len(attachments)
                label = sanitize_label(title or identifier or f"note_{note_id}")
                out_path = str(notes_dir / f"note_{idx:04d}__{label}_{run_ts}.json")
                md_path = str(notes_dir / f"note_{idx:04d}__{label}_{run_ts}.md")
                safe_message_obj = json_safe_value(message_obj)
                safe_typedef = json_safe_value(typedef)
                with Path(out_path).open("w", encoding="utf-8") as f:
                    json.dump({
                        "note_id": note_id,
                        "identifier": identifier,
                        "title": title,
                        "snippet": snippet,
                        "zdata_bytes": raw_size,
                        "gzip": gzip_used,
                        "protobuf_message": safe_message_obj,
                        "protobuf_typedef": safe_typedef,
                        "embedded_objects": embedded_objects,
                        "formatting_hints": formatting_hints,
                        "structured": {
                            "note_text": best_text,
                            "note_text_candidates": text_candidates,
                            "urls": urls,
                            "attribute_runs": attribute_runs,
                            "uti_tokens": uti_tokens,
                            "uuid_tokens": uuid_tokens,
                            "attachments": attachments,
                        },
                    }, f, ensure_ascii=True, indent=2)
                write_structured_note_markdown(
                    Path(md_path),
                    note_id,
                    identifier,
                    title,
                    snippet,
                    best_text,
                    urls,
                    attribute_runs,
                    attachments,
                )
            except Exception as exc:
                parse_error = str(exc)

            results.append([
                note_id,
                identifier,
                title,
                raw_size,
                gzip_used,
                out_path,
                md_path,
                "ok" if not parse_error else "error",
                parse_error,
                embedded_count,
                format_count,
                note_text_len,
                url_count,
                attachment_count,
                attr_run_count,
                snippet,
            ])

        try:
            import csv
            with manifest_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "note_id",
                    "identifier",
                    "title",
                    "zdata_bytes",
                    "gzip",
                    "json_path",
                    "md_path",
                    "status",
                    "error",
                    "embedded_count",
                    "format_hint_count",
                    "note_text_len",
                    "url_count",
                    "attachment_count",
                    "attr_run_count",
                    "snippet",
                ])
                writer.writerows(results)
        except Exception as exc:
            raise RuntimeError(f"Failed to write protobuf manifest: {manifest_path} -> {exc}")

        return manifest_path
    finally:
        try:
            conn.close()
        except Exception:
            pass
