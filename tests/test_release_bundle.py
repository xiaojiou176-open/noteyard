from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from scripts.release.build_public_demo_bundle import build_bundle


def test_build_public_demo_bundle(tmp_path: Path) -> None:
    out_path = tmp_path / "public-demo.zip"

    bundle_path = build_bundle(out_path)

    assert bundle_path == out_path
    assert out_path.exists()

    with ZipFile(out_path, "r") as bundle:
        names = sorted(bundle.namelist())
        assert names == [
            "README.md",
            "sanitized-ai-artifact-priority.json",
            "sanitized-ai-next-questions.md",
            "sanitized-ai-top-findings.md",
            "sanitized-ai-triage-summary.md",
            "sanitized-case-tree.txt",
            "sanitized-operator-brief.md",
            "sanitized-verification-summary.txt",
        ]
        readme = bundle.read("README.md").decode("utf-8")
        assert "Public-Safe Demo Bundle" in readme
        assert "synthetic demo artifacts" in readme
        assert "review layer only" in readme
