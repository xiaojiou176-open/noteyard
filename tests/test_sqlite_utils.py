import sqlite3
from pathlib import Path

from notes_recovery.core.sqlite_utils import (
    build_query_profile,
    detect_schema,
    escape_like,
    list_tables,
    open_sqlite_readonly,
)
from notes_recovery.config import ICLOUD_PROFILE_SPEC
from notes_recovery.models import SchemaType


def test_detect_schema_icloud_minimal(tmp_path: Path) -> None:
    db_path = tmp_path / "icloud.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE ZICCLOUDSYNCINGOBJECT (Z_PK INTEGER, ZTITLE1 TEXT, ZSNIPPET TEXT)")
        conn.execute("CREATE TABLE ZICNOTEDATA (Z_PK INTEGER, ZDATA BLOB)")
        conn.commit()
    finally:
        conn.close()

    ro = open_sqlite_readonly(db_path)
    try:
        assert detect_schema(ro) == SchemaType.ICLOUD
        tables = list_tables(ro)
        assert "ZICCLOUDSYNCINGOBJECT" in tables
        profile = build_query_profile(ro, ICLOUD_PROFILE_SPEC)
        assert profile.schema == SchemaType.ICLOUD
    finally:
        ro.close()


def test_escape_like() -> None:
    value = "a%b_c\\"
    escaped = escape_like(value)
    assert "\\%" in escaped
    assert "\\_" in escaped
    assert "\\\\" in escaped
