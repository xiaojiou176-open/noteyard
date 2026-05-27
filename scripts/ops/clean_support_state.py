#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


TARGET_SPECS = [
    ("pypi-release", ".runtime-cache/pypi-release", "rerun the PyPI release preparation path"),
    ("history-rewrite-rollback", ".runtime-cache/history-rewrite-*", "only keep rewrite rollback artifacts while you still need rollback evidence"),
    ("release-staging", ".runtime-cache/release", "rerun the release packaging workflow"),
    ("publish-attempt", ".runtime-cache/pypi-publish-attempt-*", "rerun the PyPI publish attempt after credentials are ready"),
    ("pages-audit", ".runtime-cache/lighthouse-pages*", "rerun the Pages / landing verification workflow"),
    ("security-audit", ".runtime-cache/security-audit", "rerun the repo-side security audit workflow"),
    ("support-temp", ".runtime-cache/temp", "rerun the documented support workflow"),
    ("bundle-staging", ".runtime-cache/dist-bundles", "rerun the bundle build workflow"),
    ("bundle-archive", ".runtime-cache/*starter*.zip", "rerun starter bundle export if you still need archived copies"),
    ("verification-temp", ".runtime-cache/verify-*", "rerun the matching verify command if you still need a fresh temp capture"),
    ("scanner-ledger", ".runtime-cache/gitleaks-*.json", "rerun the gitleaks scan if you still need a fresh JSON ledger"),
]


def repo_root() -> Path:
    return Path.cwd().resolve()


def match_targets(root: Path) -> list[tuple[str, Path, str]]:
    matches: list[tuple[str, Path, str]] = []
    for class_name, pattern, rebuild_hint in TARGET_SPECS:
        expanded = sorted(root.glob(pattern))
        if expanded:
            for target in expanded:
                matches.append((class_name, target, rebuild_hint))
            continue

        if any(ch in pattern for ch in "*?[]"):
            continue
        matches.append((class_name, root / pattern, rebuild_hint))
    return matches


def remove_path(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return True
    shutil.rmtree(path)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preview or remove repo-local support residue under .runtime-cache/ "
            "without touching copied evidence, output/, Docker, browser profiles, or shared caches."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview removals without deleting anything")
    mode.add_argument("--apply", action="store_true", help="delete the same support residue")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mode = "apply" if args.apply else "dry-run"
    root = repo_root()
    print(
        "[clean-support-state] maintainer-only lane; it only touches repo-local "
        "support residue under .runtime-cache/ and leaves copied evidence, output/, "
        "Docker state, browser profiles, and shared caches alone."
    )

    removed = 0
    missing = 0
    for class_name, target, rebuild_hint in match_targets(root):
        rel_target = target.relative_to(root) if target.is_absolute() and target.is_relative_to(root) else target
        if target.exists():
            if mode == "dry-run":
                print(
                    f"[clean-support-state] would remove class={class_name} "
                    f"path={rel_target} rebuild='{rebuild_hint}'"
                )
            else:
                remove_path(target)
                print(
                    f"[clean-support-state] removed class={class_name} "
                    f"path={rel_target} rebuild='{rebuild_hint}'"
                )
                removed += 1
        else:
            print(f"[clean-support-state] missing class={class_name} path={rel_target}")
            missing += 1

    print(f"clean-support-state done (mode={mode}, removed={removed}, missing={missing})")
    print("next: ./.venv/bin/python scripts/ci/check_release_readiness.py --strict")
    print("next: ./.venv/bin/python scripts/release/check_docker_surface.py --metadata-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
