from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from notes_recovery.core import sqlite_utils
from notes_recovery.models import SchemaType, QueryProfileSpec


def _create_icloud_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE ZICCLOUDSYNCINGOBJECT (ZTITLE1 TEXT, ZSNIPPET TEXT)")
    conn.execute("CREATE TABLE ZICNOTEDATA (ZDATA BLOB)")
    conn.commit()
    conn.close()


def _create_legacy_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE ZNOTE (ZTITLE TEXT, ZDATEEDITED REAL)")
    conn.execute("CREATE TABLE ZNOTEBODY (ZHTMLSTRING TEXT)")
    conn.commit()
    conn.close()


def test_detect_schema_types(tmp_path: Path) -> None:
    icloud_db = tmp_path / "icloud.sqlite"
    legacy_db = tmp_path / "legacy.sqlite"
    _create_icloud_db(icloud_db)
    _create_legacy_db(legacy_db)

    conn = sqlite_utils.open_sqlite_readonly(icloud_db)
    assert sqlite_utils.detect_schema(conn) == SchemaType.ICLOUD
    conn.close()

    conn = sqlite_utils.open_sqlite_readonly(legacy_db)
    assert sqlite_utils.detect_schema(conn) == SchemaType.LEGACY
    conn.close()


def test_build_query_profile_and_escape_like(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite"
    _create_icloud_db(db_path)
    conn = sqlite_utils.open_sqlite_readonly(db_path)
    spec = QueryProfileSpec(
        name="test",
        schema=SchemaType.ICLOUD,
        required_tables=["ZICCLOUDSYNCINGOBJECT"],
        optional_tables=["ZICNOTEDATA"],
        table_columns={"ZICCLOUDSYNCINGOBJECT": ["ZTITLE1", "ZSNIPPET", "ZOTHER"]},
    )
    profile = sqlite_utils.build_query_profile(conn, spec)
    assert "ZICCLOUDSYNCINGOBJECT" in profile.available_tables
    assert profile.missing_columns["ZICCLOUDSYNCINGOBJECT"]
    conn.close()

    assert sqlite_utils.escape_like("a%b_") == "a\\%b\\_"


def test_open_sqlite_readonly_errors(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        sqlite_utils.open_sqlite_readonly(tmp_path / "missing.sqlite")


def test_open_sqlite_readonly_connect_failure(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "db.sqlite"
    db_path.write_text("x", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise sqlite3.OperationalError("boom")

    monkeypatch.setattr(sqlite_utils.sqlite3, "connect", boom)
    with pytest.raises(RuntimeError):
        sqlite_utils.open_sqlite_readonly(db_path)


def test_list_tables_and_columns_errors() -> None:
    class _BadConn:
        def execute(self, _sql):
            raise sqlite3.OperationalError("fail")

    with pytest.raises(RuntimeError):
        sqlite_utils.list_tables(_BadConn())
    assert sqlite_utils.table_columns(_BadConn(), "t") == set()
