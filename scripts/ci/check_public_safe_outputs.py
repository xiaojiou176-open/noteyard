from __future__ import annotations

import re
import sys
from pathlib import Path


ABSOLUTE_PATH_PATTERN = re.compile(
    "|".join(
        (
            re.escape("/" + "Users" + "/"),
            re.escape("/" + "home" + "/"),
            r"[A-Za-z]:\\" + "Users" + r"\\",
        )
    )
)
FORBIDDEN_TOKENS = (
    "\"python_executable\"",
    "\"hostname\"",
    "\"cwd\": \"/",
)
DEFAULT_SURFACES = (
    "notes_recovery/resources/demo",
)


def _iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if root.is_file():
        return [root]
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".txt", ".md", ".json", ".jsonl", ".csv", ".html"}:
            files.append(path)
    return files


def collect_public_safe_output_errors(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for root in paths:
        if not root.exists():
            errors.append(f"missing public-safe surface: {root}")
            continue
        for path in _iter_text_files(root):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if ABSOLUTE_PATH_PATTERN.search(text):
                errors.append(f"absolute path found in public-safe surface: {path}")
            for token in FORBIDDEN_TOKENS:
                if token in text:
                    errors.append(f"forbidden host token found in public-safe surface: {path} -> {token}")
    return errors


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    repo_root = Path(__file__).resolve().parents[2]
    targets = [repo_root / item for item in argv] if argv else [repo_root / item for item in DEFAULT_SURFACES]
    errors = collect_public_safe_output_errors(targets)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("public-safe output check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
