from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


REPO_ROOT = Path(__file__).resolve().parents[2]
STARTER_ROOT = REPO_ROOT / "starter-bundles"


def _iter_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def build_bundle(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not STARTER_ROOT.exists():
        raise RuntimeError(f"Missing starter bundle root: {STARTER_ROOT}")

    files = _iter_files(STARTER_ROOT)
    if not files:
        raise RuntimeError(f"Starter bundle root is empty: {STARTER_ROOT}")

    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as bundle:
        for source in files:
            bundle.write(source, arcname=str(source.relative_to(STARTER_ROOT)))
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output zip path")
    args = parser.parse_args()
    out_path = Path(args.out).expanduser().resolve()
    build_bundle(out_path)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
