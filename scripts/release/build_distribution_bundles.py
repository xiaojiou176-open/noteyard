from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


REPO_ROOT = Path(__file__).resolve().parents[2]

BUNDLE_SPECS = (
    {
        "key": "codex",
        "archive_name": "noteyard-codex-plugin-v0.1.0.zip",
        "root_name": "noteyard-codex-plugin",
        "source_dir": REPO_ROOT / "plugins" / "noteyard-codex-plugin",
    },
    {
        "key": "claude",
        "archive_name": "noteyard-claude-plugin-v0.1.0.zip",
        "root_name": "noteyard-claude-plugin",
        "source_dir": REPO_ROOT / "plugins" / "noteyard-claude-plugin",
    },
    {
        "key": "openclaw",
        "archive_name": "noteyard-openclaw-bundle-v0.1.0.zip",
        "root_name": "noteyard-openclaw-bundle",
        "source_dir": REPO_ROOT / "plugins" / "noteyard-openclaw-bundle",
    },
)


def _iter_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def _write_bundle(output_path: Path, root_name: str, source_dir: Path) -> None:
    if not source_dir.exists():
        raise RuntimeError(f"Missing bundle source directory: {source_dir}")
    files = _iter_files(source_dir)
    if not files:
        raise RuntimeError(f"Bundle source is empty: {source_dir}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as bundle:
        for file_path in files:
            rel_path = file_path.relative_to(source_dir)
            bundle.write(file_path, arcname=str(Path(root_name) / rel_path))


def build_distribution_bundles(out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    bundles: list[dict[str, str]] = []
    for spec in BUNDLE_SPECS:
        archive_path = out_dir / str(spec["archive_name"])
        _write_bundle(archive_path, str(spec["root_name"]), Path(spec["source_dir"]))
        bundles.append(
            {
                "key": str(spec["key"]),
                "archive": str(archive_path),
                "root_name": str(spec["root_name"]),
                "source_dir": str(Path(spec["source_dir"]).relative_to(REPO_ROOT)),
            }
        )

    manifest_path = out_dir / "distribution_manifest.json"
    manifest = {"bundles": bundles}
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return {"bundles": bundles, "manifest": str(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, help="Output directory for built distribution bundles")
    args = parser.parse_args()
    result = build_distribution_bundles(Path(args.out_dir).expanduser().resolve())
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
