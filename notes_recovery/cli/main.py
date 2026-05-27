from __future__ import annotations

from typing import Optional

from notes_recovery.cli.handlers import run_command
from notes_recovery.cli.parser import build_parser
from notes_recovery.core.pipeline import configure_case_manifest


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_case_manifest(args)
    return run_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
