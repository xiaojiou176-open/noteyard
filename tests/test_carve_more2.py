from __future__ import annotations

import gzip
from pathlib import Path

import notes_recovery.services.carve as carve


def test_carve_helpers(tmp_path: Path) -> None:
    data = b"hello world"
    gz = gzip.compress(data)

    file_path = tmp_path / "blob.bin"
    file_path.write_bytes(b"xxxx" + gz + b"yyyy")

    offsets = list(carve.find_gzip_offsets(file_path, chunk_size=8))
    assert offsets

    decoded = carve.try_decompress_window(gz, "gzip")
    assert decoded == data

    ratio = carve.text_printable_ratio("hello\nworld")
    assert ratio > 0.5

    assert carve.should_accept_carved_text("hello world", min_text_len=5, min_ratio=0.3)

    algos = carve.normalize_carve_algorithms("gzip,zlib")
    assert "gzip" in algos
    assert "zlib" in algos

    offsets = list(carve.find_compressed_offsets(file_path, chunk_size=16, algorithms=["gzip"]))
    assert offsets

    data, algo = carve.try_decompress_at(
        file_path,
        offsets[0][0],
        window_size=200,
        algorithms=["gzip"],
        max_window_size=256,
        max_output_bytes=1024,
        warned_missing=set(),
    )
    assert data is not None
    assert algo == "gzip"
