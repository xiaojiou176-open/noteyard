import gzip
from pathlib import Path

from notes_recovery.services.carve import carve_gzip


def test_carve_gzip_finds_payload(tmp_path: Path) -> None:
    text = "forensics_keyword_payload"
    payload = gzip.compress(text.encode("utf-8"))
    data = b"\x00" * 64 + payload + b"\x00" * 32
    db_path = tmp_path / "sample.sqlite"
    db_path.write_bytes(data)

    out_dir = tmp_path / "Recovered_Blobs"
    carve_gzip(
        db_path=db_path,
        out_dir=out_dir,
        keyword="forensics_keyword_payload",
        max_hits=5,
        window_size=2048,
        min_text_len=8,
        min_text_ratio=0.2,
        algorithms=["gzip"],
        max_output_mb=1,
    )

    manifest = out_dir / "manifest.jsonl"
    assert manifest.exists()
    outputs = list(out_dir.glob("blob_*.txt"))
    assert outputs
    combined = "\n".join(p.read_text(encoding="utf-8") for p in outputs)
    assert "forensics_keyword_payload" in combined
