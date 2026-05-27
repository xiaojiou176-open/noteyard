import struct
from pathlib import Path

from notes_recovery.config import WAL_MAGIC_LE
from notes_recovery.services.wal import wal_extract


def _write_wal(path: Path, page_size: int = 512) -> None:
    header = struct.pack(">I", WAL_MAGIC_LE
    ) + struct.pack("<7I", 1, page_size, 0, 0, 0, 0, 0)
    frame_header = struct.pack("<6I", 1, 0, 0, 0, 0, 0)
    payload = b"Alpha" + b"\x00" * (page_size - 5)
    path.write_bytes(header + frame_header + payload)


def test_wal_extract_strings(tmp_path: Path) -> None:
    root_dir = tmp_path / "root"
    out_dir = tmp_path / "out"
    root_dir.mkdir()
    wal_path = root_dir / "NoteStore.sqlite-wal"
    _write_wal(wal_path)

    manifest = wal_extract(
        root_dir=root_dir,
        out_dir=out_dir,
        keyword="Alpha",
        max_frames=10,
        page_size_override=0,
        dump_pages=True,
        dump_only_duplicates=False,
        strings_on=True,
        strings_min_len=4,
        strings_max_chars=200,
        run_ts="20260101_000000",
        wal_path=wal_path,
    )

    assert manifest.exists()
    wal_dirs = list(out_dir.glob("*"))
    assert wal_dirs
    strings_dirs = list((wal_dirs[0] / "Strings").glob("*.txt"))
    assert strings_dirs
