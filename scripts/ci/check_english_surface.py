from __future__ import annotations

import re
import sys
from pathlib import Path


HAN_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

RUNTIME_SURFACE_PATHS = (
    "notes_recovery",
)


def collect_english_surface_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []
    for rel_path in RUNTIME_SURFACE_PATHS:
        target = repo_root / rel_path
        if not target.exists():
            errors.append(f"missing runtime surface path: {rel_path}")
            continue
        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() in {".pyc", ".sqlite", ".db", ".shm", ".wal", ".png", ".svg"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if HAN_PATTERN.search(line):
                    errors.append(f"non-English runtime text detected: {path.relative_to(repo_root)}:{lineno}")
                    break
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors = collect_english_surface_errors(repo_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("english surface check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
