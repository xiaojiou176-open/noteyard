from notes_recovery.core.sqlite_utils import detect_schema, open_sqlite_readonly
from notes_recovery.models import SchemaType

def test_detect_schema_icloud(data_dir) -> None:
    db_path = data_dir / "icloud_min.sqlite"
    conn = open_sqlite_readonly(db_path)
    try:
        assert detect_schema(conn) == SchemaType.ICLOUD
    finally:
        conn.close()


def test_detect_schema_legacy(data_dir) -> None:
    db_path = data_dir / "legacy_min.sqlite"
    conn = open_sqlite_readonly(db_path)
    try:
        assert detect_schema(conn) == SchemaType.LEGACY
    finally:
        conn.close()
