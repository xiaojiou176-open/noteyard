import gzip
from pathlib import Path

import pytest

from notes_recovery.services import carve


def test_normalize_carve_algorithms():
    assert "gzip" in carve.normalize_carve_algorithms("gzip")
    all_algos = carve.normalize_carve_algorithms("all")
    assert "gzip" in all_algos
    with pytest.raises(RuntimeError):
        carve.normalize_carve_algorithms("unknown")


def test_carve_gzip_finds_payload(tmp_path: Path) -> None:
    payload = gzip.compress(b"Alpha Beta Gamma")
    blob = b"\x00" * 10 + payload + b"\x00" * 10
    db_path = tmp_path / "blob.bin"
    db_path.write_bytes(blob)

    out_dir = tmp_path / "out"
    carve.carve_gzip(
        db_path=db_path,
        out_dir=out_dir,
        keyword="Alpha",
        max_hits=2,
        window_size=512,
        min_text_len=5,
        min_text_ratio=0.1,
        algorithms=["gzip"],
        max_output_mb=1,
    )

    hits = list(out_dir.glob("blob_*.txt"))
    assert hits
