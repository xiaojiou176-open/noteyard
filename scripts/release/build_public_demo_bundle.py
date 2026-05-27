from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = REPO_ROOT / "notes_recovery" / "resources" / "demo"

REQUIRED_FILES = (
    "sanitized-case-tree.txt",
    "sanitized-verification-summary.txt",
    "sanitized-operator-brief.md",
    "sanitized-ai-triage-summary.md",
    "sanitized-ai-top-findings.md",
    "sanitized-ai-next-questions.md",
    "sanitized-ai-artifact-priority.json",
)


def build_bundle(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    missing = [name for name in REQUIRED_FILES if not (DEMO_ROOT / name).exists()]
    if missing:
        raise RuntimeError(f"Missing demo resource(s): {', '.join(missing)}")

    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as bundle:
        bundle.writestr(
            "README.md",
            "\n".join(
                [
                    "# NotesRecover Public-Safe Demo Bundle",
                    "",
                    "This bundle contains tracked synthetic demo artifacts for the public-safe first-look path.",
                    "",
                    "Included files:",
                    "- sanitized-case-tree.txt",
                    "- sanitized-verification-summary.txt",
                    "- sanitized-operator-brief.md",
                    "- sanitized-ai-triage-summary.md",
                    "- sanitized-ai-top-findings.md",
                    "- sanitized-ai-next-questions.md",
                    "- sanitized-ai-artifact-priority.json",
                    "",
                    "These files are synthetic proof surfaces, not evidence from a live Apple Notes incident.",
                    "The AI proof files demonstrate the review layer only; they do not make AI the recovery engine.",
                ]
            )
            + "\n",
        )
        for name in REQUIRED_FILES:
            source = DEMO_ROOT / name
            bundle.write(source, arcname=name)
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
