from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "ops"
    / "clean_support_state.py"
)


def write_file(path: Path, content: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class CleanSupportStateTests(unittest.TestCase):
    def test_dry_run_lists_supported_runtime_residue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_file(root / ".runtime-cache" / "pypi-release" / "artifact.whl")
            write_file(root / ".runtime-cache" / "history-rewrite-20260407T172244" / "rollback.bundle")
            write_file(root / ".runtime-cache" / "lighthouse-pages" / "report.html")
            write_file(root / ".runtime-cache" / "test-starter-bundles.zip")

            result = subprocess.run(
                ["python3", str(SCRIPT), "--dry-run"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("class=pypi-release path=.runtime-cache/pypi-release", result.stdout)
        self.assertIn(
            "class=history-rewrite-rollback path=.runtime-cache/history-rewrite-20260407T172244",
            result.stdout,
        )
        self.assertIn("class=pages-audit path=.runtime-cache/lighthouse-pages", result.stdout)
        self.assertIn("class=bundle-archive path=.runtime-cache/test-starter-bundles.zip", result.stdout)

    def test_apply_removes_matching_support_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            keep = root / ".runtime-cache" / "other" / "keep.txt"
            write_file(keep)
            target = root / ".runtime-cache" / "pypi-publish-attempt-20260407T173022" / "state.json"
            write_file(target)

            result = subprocess.run(
                ["python3", str(SCRIPT), "--apply"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(target.parent.exists())
            self.assertTrue(keep.exists())


if __name__ == "__main__":
    unittest.main()
