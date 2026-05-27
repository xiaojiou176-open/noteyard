from __future__ import annotations

import sqlite3
from pathlib import Path

import notes_recovery.services.query as query


def test_query_helpers(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE notes (title TEXT, body TEXT)")
    conn.execute("INSERT INTO notes VALUES ('hello', 'world')")
    conn.commit()

    cols, rows = query.run_query(conn, "SELECT title, body FROM notes")
    assert cols == ["title", "body"]
    assert rows

    select_list = query.build_select_list("n", ["title", "body"])
    assert "n.title" in select_list

    out_path = tmp_path / "out.csv"
    query.write_csv(out_path, cols, rows)
    assert out_path.exists()
    conn.close()
