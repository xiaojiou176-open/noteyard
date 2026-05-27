from __future__ import annotations

from pathlib import Path

from scripts.ci.contracts import (
    BASELINE_TESTS,
    CONTRIBUTING_VERIFICATION_REQUIRED_TOKENS,
    DEEP_REALISM_JOB_NAME,
    DEEP_REALISM_TESTS,
    HOST_SAFETY_DOC_TOKENS_BY_FILE,
    README_VERIFICATION_REQUIRED_TOKENS,
    RUNTIME_HYGIENE_TOKENS,
)
from scripts.ci.check_docs_surface import collect_docs_surface_errors
from scripts.ci.check_discovery_surface_contract import collect_discovery_surface_errors
from scripts.ci.check_host_safety_contract import collect_host_safety_contract_errors
from scripts.ci.check_optional_surface_contract import collect_optional_surface_contract_errors
from scripts.ci.check_public_story_truth import collect_public_story_truth_errors
from scripts.ci.check_repo_hygiene import (
    collect_hygiene_errors,
    collect_open_source_boundary_errors,
)
from scripts.ci.check_verification_contract import collect_verification_contract_errors


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_contributing_verification_block() -> str:
    baseline_lines = [
        ".venv/bin/notes-recovery --help",
        ".venv/bin/notes-recovery demo",
        ".venv/bin/python -m pytest \\",
        *[f"  {test_path} \\" for test_path in BASELINE_TESTS],
        "  -q",
    ]
    deep_realism_lines = [
        ".venv/bin/python -m pytest \\",
        *[f"  {test_path} \\" for test_path in DEEP_REALISM_TESTS],
        "  -q",
    ]
    return "\n".join(
        [
            "# Contributing",
            *CONTRIBUTING_VERIFICATION_REQUIRED_TOKENS,
            *baseline_lines,
            *deep_realism_lines,
            ".venv/bin/python -m pytest tests/ -q",
        ]
    )


def test_docs_surface_passes_for_minimal_repo(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "# NoteStore Lab",
                "",
                "[License](LICENSE)",
                "[Public Proof](proof.html)",
                "[LLMs](llms.txt)",
                "[Security](SECURITY.md)",
                "[Contributing](CONTRIBUTING.md)",
                "[Support](SUPPORT.md)",
                "[Agent Navigation](AGENTS.md)",
                "[Claude Navigation](CLAUDE.md)",
                "",
                "`notes-recovery`",
            ]
        ),
    )
    _write(tmp_path / "proof.html", "<html><body>proof</body></html>\n")
    _write(tmp_path / "llms.txt", "# NoteStore Lab\n")
    _write(tmp_path / "LICENSE", "MIT\n")
    _write(tmp_path / "CONTRIBUTING.md", "# Contributing\n")
    _write(tmp_path / "SECURITY.md", "# Security\n")
    _write(tmp_path / "SUPPORT.md", "# Support\n")
    _write(tmp_path / "AGENTS.md", "# Agent Navigation\n")
    _write(tmp_path / "CLAUDE.md", "# Claude Navigation\n")
    _write(tmp_path / ".env.example", "NOTES_CASE_HMAC_KEY=\nNOTES_CASE_PGP_KEY=\nNOTES_CASE_PGP_HOME=\n")

    assert collect_docs_surface_errors(tmp_path) == []


def test_docs_surface_rejects_removed_docs_tree(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "# NoteStore Lab",
                "",
                "[License](LICENSE)",
                "[Public Proof](proof.html)",
                "[LLMs](llms.txt)",
                "[Security](SECURITY.md)",
                "[Contributing](CONTRIBUTING.md)",
                "[Support](SUPPORT.md)",
                "[Agent Navigation](AGENTS.md)",
                "[Claude Navigation](CLAUDE.md)",
                "",
                "`notes-recovery`",
            ]
        ),
    )
    _write(tmp_path / "proof.html", "<html><body>proof</body></html>\n")
    _write(tmp_path / "llms.txt", "# NoteStore Lab\n")
    _write(tmp_path / "LICENSE", "MIT\n")
    _write(tmp_path / "CONTRIBUTING.md", "# Contributing\n")
    _write(tmp_path / "SECURITY.md", "# Security\n")
    _write(tmp_path / "SUPPORT.md", "# Support\n")
    _write(tmp_path / "AGENTS.md", "# Agent Navigation\n")
    _write(tmp_path / "CLAUDE.md", "# Claude Navigation\n")
    _write(tmp_path / ".env.example", "NOTES_CASE_HMAC_KEY=\nNOTES_CASE_PGP_KEY=\nNOTES_CASE_PGP_HOME=\n")
    _write(tmp_path / "docs" / "index.html", "<html></html>\n")

    errors = collect_docs_surface_errors(tmp_path)

    assert any("docs/ must not exist" in error for error in errors)


def test_repo_hygiene_detects_missing_required_ignore_markers(tmp_path: Path) -> None:
    _write(tmp_path / ".gitignore", "__pycache__/\n")
    errors = collect_hygiene_errors(tmp_path)

    assert any(".agents/" in error for error in errors)
    assert any(".agent/" in error for error in errors)
    assert any(".codex/" in error for error in errors)
    assert any(".claude/" in error for error in errors)
    assert any("log/" in error for error in errors)
    assert any("*.log" in error for error in errors)


def test_repo_hygiene_detects_missing_precommit_tokens(tmp_path: Path) -> None:
    _write(
        tmp_path / ".gitignore",
        ".agents/\n.agent/\n.codex/\n.claude/\n.runtime-cache/\nlog/\nlogs/\n*.log\n",
    )
    _write(
        tmp_path / ".pre-commit-config.yaml",
        "\n".join(
            [
                "repos:",
                "  - repo: local",
                "    hooks:",
                "      - id: repo-hygiene",
                "        entry: python scripts/ci/check_repo_hygiene.py --mode hygiene",
            ]
        ),
    )
    _write(tmp_path / ".gitleaks.toml", "[extend]\nuseDefault = true\n")
    _write(tmp_path / ".env.example", "NOTES_CASE_HMAC_KEY=\n")

    errors = collect_hygiene_errors(tmp_path)
    assert any("missing required token: gitleaks" in error for error in errors)
    assert any("missing required token: git-secrets" in error for error in errors)
    assert any("missing required token: actionlint workflow lint" in error for error in errors)
    assert any("missing required token: check_commit_identity.py" in error for error in errors)
    assert any("missing required token: check_sensitive_surface.py" in error for error in errors)
    assert any("missing required token: check_host_safety_contract.py" in error for error in errors)
    assert any("open-source-boundary" in error for error in errors)
    assert any(".env.example is missing required token: NOTES_CASE_PGP_KEY" in error for error in errors)


def test_repo_hygiene_detects_missing_dependabot_config(tmp_path: Path) -> None:
    _write(
        tmp_path / ".gitignore",
        "\n".join(
            [
                ".agents/",
                ".agent/",
                ".codex/",
                ".claude/",
                ".runtime-cache/",
                "log/",
                "logs/",
                "*.log",
                ".env",
                ".env.*",
                "!.env.example",
                "*.pem",
                "*.key",
                "*.p12",
                "*.jks",
                "*.keystore",
                ".npmrc",
                ".pypirc",
                "credentials.json",
                "secrets.yml",
                "secrets.yaml",
            ]
        )
        + "\n",
    )
    _write(
        tmp_path / ".pre-commit-config.yaml",
        "\n".join(
            [
                "default_install_hook_types:",
                "  - pre-commit",
                "  - pre-push",
                "repos:",
                "  - repo: local",
                "    hooks:",
                "      - id: gitleaks",
                "        name: gitleaks tracked-tree scan",
                "        entry: gitleaks dir .",
                "      - id: git-secrets",
                "        name: git-secrets recursive scan",
                "        entry: git-secrets --scan -r .",
                "      - id: actionlint",
                "        name: actionlint workflow lint",
                "        entry: actionlint",
                "      - id: repo-hygiene",
                "        entry: python scripts/ci/check_repo_hygiene.py --mode hygiene",
                "      - id: open-source-boundary",
                "        entry: python scripts/ci/check_repo_hygiene.py --mode open-source-boundary",
                "      - id: runtime-hygiene",
                "        entry: python scripts/ci/check_runtime_hygiene.py",
                "      - id: english-surface",
                "        entry: python scripts/ci/check_english_surface.py",
                "      - id: public-safe-outputs",
                "        entry: python scripts/ci/check_public_safe_outputs.py",
                "      - id: host-safety",
                "        entry: python scripts/ci/check_host_safety_contract.py",
                "      - id: commit-identity",
                "        entry: python scripts/ci/check_commit_identity.py --mode all",
                "      - id: github-security-alerts-push",
                "        entry: python scripts/ci/check_github_security_alerts.py",
                "        stages:",
                "          - pre-push",
                "      - id: baseline-smoke",
                "        entry: baseline-smoke",
                "        stages:",
                "          - pre-push",
                "      - id: sensitive-surface",
                "        entry: python scripts/ci/check_sensitive_surface.py",
                "      - id: pypi-publish-readiness",
                "        entry: python scripts/release/check_pypi_publish_readiness.py",
                "        stages:",
                "          - pre-push",
            ]
        )
        + "\n",
    )
    _write(tmp_path / ".gitleaks.toml", "[extend]\nuseDefault = true\n")
    _write(
        tmp_path / ".env.example",
        "NOTES_CASE_HMAC_KEY=\nNOTES_CASE_PGP_KEY=\nNOTES_CASE_PGP_HOME=\n",
    )

    errors = collect_hygiene_errors(tmp_path)

    assert any("missing .github/dependabot.yml" in error for error in errors)


def test_open_source_boundary_detects_unpinned_workflow(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "git history",
                "pull request diffs",
                "forks",
                "mirrors",
                "downloaded clones",
                "branch protection",
                "secret scanning",
                "hosting settings",
                "required pull request reviews",
                "xiaojiou176",
                "opt-in integrations",
                "check_release_readiness.py",
            ]
        ),
    )
    _write(
        tmp_path / "SECURITY.md",
        "# Security\nGitHub Security Advisories\nsingle-maintainer owner\n",
    )
    _write(
        tmp_path / "tests" / "data" / "README.md",
        "\n".join(
            [
                "# Test Data",
                "synthetic",
                "not exported from a live Apple Notes account",
                "verification inputs",
            ]
        ),
    )
    _write(tmp_path / "CODEOWNERS", "* @owner\n")
    _write(tmp_path / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml", "name: Bug report\n")
    _write(tmp_path / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml", "name: Feature request\n")
    _write(tmp_path / ".github" / "pull_request_template.md", "## Summary\n")
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "\n".join(
            [
                "name: CI",
                "jobs:",
                "  test:",
                "    steps:",
                "      - uses: actions/checkout@v4",
            ]
        ),
    )
    _write(tmp_path / "scripts" / "ci" / "check_release_readiness.py", "print('ok')\n")

    errors = collect_open_source_boundary_errors(tmp_path)
    assert any("permissions" in error for error in errors)
    assert any("check_commit_identity.py" in error for error in errors)
    assert any("check_sensitive_surface.py" in error for error in errors)
    assert any("check_github_security_alerts.py" in error for error in errors)
    assert any("rhysd/actionlint@" in error for error in errors)
    assert any("not SHA pinned" in error for error in errors)


def test_verification_contract_passes_for_aligned_surface(tmp_path: Path) -> None:
    baseline_lines = [
        "          notes-recovery --help",
        "          notes-recovery demo",
        "          python -m pytest \\",
        *[f"            {test_path} \\" for test_path in BASELINE_TESTS],
        "            -q",
    ]
    deep_realism_lines = [
        "          python -m pytest \\",
        *[f"            {test_path} \\" for test_path in DEEP_REALISM_TESTS],
        "            -q",
    ]
    workflow_block = "\n".join(
        [
            "name: CI",
            "on:",
            "  workflow_dispatch:",
            "  schedule:",
            "    - cron: '17 8 * * *'",
            "jobs:",
            "  baseline:",
            "    steps:",
            "      - name: Baseline smoke",
            "        run: |",
            *baseline_lines,
            f"  {DEEP_REALISM_JOB_NAME}:",
            "    steps:",
            "      - name: Deep realism smoke",
            "        run: |",
            *deep_realism_lines,
        ]
    )
    readme_text = "\n".join(
        [
            "# NoteStore Lab",
            *README_VERIFICATION_REQUIRED_TOKENS,
            "See CONTRIBUTING.md for the canonical baseline smoke and full suite commands.",
            "[Contributing](CONTRIBUTING.md)",
        ]
    )
    contributing_text = _build_contributing_verification_block()
    _write(tmp_path / "README.md", readme_text)
    _write(tmp_path / "llms.txt", "# NoteStore Lab\n")
    _write(tmp_path / "CONTRIBUTING.md", contributing_text)
    _write(tmp_path / ".github" / "workflows" / "ci.yml", workflow_block)

    assert collect_verification_contract_errors(tmp_path) == []


def test_verification_contract_detects_readme_drift(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "# NoteStore Lab\nbaseline smoke\nfull suite\noptional surfaces\n.venv/bin/python -m pytest tests/\n",
    )
    _write(
        tmp_path / "CONTRIBUTING.md",
        _build_contributing_verification_block(),
    )
    _write(tmp_path / ".github" / "workflows" / "ci.yml", "name: CI\njobs:\n")

    errors = collect_verification_contract_errors(tmp_path)
    assert any("must not claim" in error for error in errors)


def test_verification_contract_detects_baseline_deep_mix(tmp_path: Path) -> None:
    mixed_baseline = "\n".join(
        [
            "name: CI",
            "on:",
            "  workflow_dispatch:",
            "  schedule:",
            "    - cron: '17 8 * * *'",
            "jobs:",
            "  baseline:",
            "    steps:",
            "      - name: Baseline smoke",
            "        run: |",
            "          notes-recovery --help",
            "          notes-recovery demo",
            "          python -m pytest \\",
            *[f"            {test_path} \\" for test_path in BASELINE_TESTS],
            *[f"            {test_path} \\" for test_path in DEEP_REALISM_TESTS],
            "            -q",
        ]
    )
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "# NoteStore Lab",
                *README_VERIFICATION_REQUIRED_TOKENS,
                "[Contributing](CONTRIBUTING.md)",
            ]
        ),
    )
    _write(tmp_path / "CONTRIBUTING.md", _build_contributing_verification_block())
    _write(tmp_path / ".github" / "workflows" / "ci.yml", mixed_baseline)

    errors = collect_verification_contract_errors(tmp_path)
    assert any("must not include deep realism test" in error for error in errors)


def test_runtime_hygiene_tokens_track_shared_contract() -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")

    for token in RUNTIME_HYGIENE_TOKENS:
        assert token in readme_text


def test_host_safety_contract_passes_for_current_repo() -> None:
    repo_root = Path(".")

    assert collect_host_safety_contract_errors(repo_root) == []


def test_host_safety_tokens_track_shared_contract() -> None:
    for relative_path, tokens in HOST_SAFETY_DOC_TOKENS_BY_FILE.items():
        text = Path(relative_path).read_text(encoding="utf-8").casefold()
        for token in tokens:
            assert token.casefold() in text


def test_public_story_truth_passes_for_truthful_surface(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "# Apple Notes Recovery on Copied Evidence for macOS",
                "",
                "[Changelog](CHANGELOG.md)",
            ]
        ),
    )
    _write(
        tmp_path / "CHANGELOG.md",
        "\n".join(
            [
                "# Changelog",
                "",
                "## [Unreleased]",
                "",
                "- No public release or Pages site is published yet.",
            ]
        ),
    )
    _write(
        tmp_path / "notes_recovery" / "cli" / "tail_handlers.py",
        'CHANGELOG_URL = "https://github.com/xiaojiou176-open/noteyard/blob/main/CHANGELOG.md"\n',
    )
    _write(
        tmp_path / "DISTRIBUTION.md",
        "# Distribution\nserver.json records the intended PyPI package identifier and version.\n",
    )
    _write(
        tmp_path / "INTEGRATIONS.md",
        "# Integrations\nUse DISTRIBUTION.md for current listing truth.\n## Forbidden Claims\n- \"registry metadata points at the live PyPI package\" without fresh PyPI read-back\n",
    )

    assert collect_public_story_truth_errors(tmp_path) == []


def test_public_story_truth_detects_stale_release_and_pages_claims(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "# NoteStore Lab",
                "",
                "[Release](https://github.com/xiaojiou176-open/noteyard/releases/tag/v0.1.0)",
            ]
        ),
    )
    _write(
        tmp_path / "CHANGELOG.md",
        "\n".join(
            [
                "# Changelog",
                "",
                "- Static docs homepage",
                "- Pages docs surface are now live",
                "- Public visual asset set: hero image, case-flow image, social-preview image, and demo GIF",
                "- First milestone release notes and social copy draft under `docs/releases/`",
            ]
        ),
    )
    _write(
        tmp_path / "notes_recovery" / "cli" / "tail_handlers.py",
        'RELEASE_URL = "https://github.com/xiaojiou176-open/noteyard/releases/tag/v0.1.0"\n',
    )
    _write(
        tmp_path / "DISTRIBUTION.md",
        "# Distribution\nThe referenced pypi package for this repository already exists on PyPI.\nregistry metadata points at the live PyPI package.\n",
    )

    errors = collect_public_story_truth_errors(tmp_path)
    assert any("tag-specific release URL" in error for error in errors)
    assert any("Pages docs surface are now live" in error for error in errors)
    assert any("Public visual asset set" in error for error in errors)
    assert any("already exists on PyPI" in error for error in errors)


def test_discovery_surface_contract_passes_for_aligned_surface(tmp_path: Path) -> None:
    _write(
        tmp_path / "llms.txt",
        "# NoteStore Lab\nnotes-recovery\nnotes-recovery-mcp\nCodex\nClaude Code\nMCP\nNot a primary front-door claim\nno shipped hosted API\ngood current examples of hosts\n.codex/config.toml\n.mcp.json\nremote-connector-first hosts\nOpenClaw-style hosts\nnotes-recovery ai-review --demo\nnotes-recovery ask-case --demo --question \"What should I inspect first?\"\n.venv/bin/python -m notes_recovery.mcp.server --case-dir ./output/Notes_Forensics_<run_ts>\n",
    )
    _write(tmp_path / "robots.txt", "User-agent: *\nAllow: /\nSitemap: https://xiaojiou176-open.github.io/noteyard/sitemap.xml\n")
    _write(
        tmp_path / "sitemap.xml",
        "\n".join(
            [
                "<urlset>",
                "https://xiaojiou176-open.github.io/noteyard/",
                "https://xiaojiou176-open.github.io/noteyard/llms.txt",
                "https://xiaojiou176-open.github.io/noteyard/robots.txt",
                "</urlset>",
            ]
        ),
    )
    _write(
        tmp_path / "404.html",
        "\n".join(
            [
                "Page not found",
                "Return to the landing page",
                "Open the GitHub repository",
                "Open the release feed",
            ]
        ),
    )
    _write(
        tmp_path / "site.webmanifest",
        "\n".join(
            [
                '{',
                '  "name": "NoteStore Lab",',
                '  "short_name": "NoteStore Lab",',
                '  "start_url": "/noteyard/",',
                '  "scope": "/noteyard/",',
                '  "theme_color": "#16212b",',
                '  "background_color": "#f5f1e8",',
                '  "icons": [',
                '    {"src": "assets/brand/icon-192.png"},',
                '    {"src": "assets/brand/icon-512.png"}',
                "  ]",
                '}',
            ]
        ),
    )
    for rel_path in (
        "assets/brand/notestorelab-mark.svg",
        "assets/brand/favicon-32.png",
        "assets/brand/apple-touch-icon.png",
        "assets/brand/icon-192.png",
        "assets/brand/icon-512.png",
    ):
        _write(tmp_path / rel_path, "asset\n")
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "# NoteStore Lab",
                "[LLMs Guide](./llms.txt)",
                "Codex",
                "Claude Code",
                "good current examples of hosts",
                "OpenClaw-style hosts",
                ".codex/config.toml",
                ".mcp.json",
                "remote-connector-first hosts",
            ]
        ),
    )
    _write(
        tmp_path / "INTEGRATIONS.md",
        "\n".join(
            [
                "llms.txt",
                ".venv/bin/python -m notes_recovery.mcp.server",
                "Codex / Claude Code",
                "good current examples of hosts",
                "OpenClaw wrapper example",
                "repo-owned skills pack",
                ".codex/config.toml",
                ".mcp.json",
                "[mcp_servers.notestorelab]",
                "../.venv/bin/python",
                'cwd = ".."',
                '"mcpServers"',
                "remote-connector-first hosts",
            ]
        ),
    )
    _write(
        tmp_path / "index.html",
        "\n".join(
            [
                "Follow the 4-command proof path",
                "See the public proof boundary",
                "4 operator-first steps in under 5 minutes",
                "One case, three consumers",
                "Public proof boundary",
                "LLMs guide",
                "Builder path: Codex and Claude Code",
                "OpenClaw-style hosts",
                "Fastest host smoke",
                "Registration command:",
                "twitter:title",
                "canonical",
                "og:site_name",
                "og:locale",
                'rel="icon"',
                "apple-touch-icon",
                "site.webmanifest",
                "brand-mark",
                'hreflang=\"x-default\"',
                '"inLanguage": "en-US"',
                "Comparison path only.",
                ".codex/config.toml",
                ".mcp.json",
                "../.venv/bin/python",
                'cwd = ".."',
            ]
        ),
    )
    _write(
        tmp_path / "SUPPORT.md",
        "\n".join(
            [
                "which host you used",
                "Codex",
                "Claude Code",
                "OpenHands",
                "OpenCode",
                "another local runner",
            ]
        ),
    )

    assert collect_discovery_surface_errors(tmp_path) == []


def test_discovery_surface_contract_detects_missing_llms_tokens(tmp_path: Path) -> None:
    _write(tmp_path / "llms.txt", "# NoteStore Lab\n")
    _write(tmp_path / "robots.txt", "User-agent: *\nAllow: /\n")
    _write(tmp_path / "sitemap.xml", "<urlset></urlset>\n")
    _write(tmp_path / "404.html", "Page not found\n")
    _write(tmp_path / "site.webmanifest", "{}\n")
    _write(tmp_path / "README.md", "# NoteStore Lab\n")
    _write(tmp_path / "INTEGRATIONS.md", "# Builder Guide\n")
    _write(tmp_path / "SUPPORT.md", "# Support\n")
    _write(tmp_path / "index.html", "<html></html>\n")

    errors = collect_discovery_surface_errors(tmp_path)
    assert any("llms.txt is missing required token: Codex" in error for error in errors)
    assert any("llms.txt is missing discovery token: good current examples of hosts" in error for error in errors)
    assert any("missing discovery asset file: assets/brand/notestorelab-mark.svg" in error for error in errors)
    assert any("site.webmanifest is missing required token: \"name\": \"NoteStore Lab\"" in error for error in errors)
    assert any("README.md is missing discovery token" in error for error in errors)
    assert any("INTEGRATIONS.md is missing discovery token: [mcp_servers.notestorelab]" in error for error in errors)
    assert any('INTEGRATIONS.md is missing discovery token: cwd = ".."' in error for error in errors)
    assert any("SUPPORT.md is missing discovery token: Codex" in error for error in errors)


def test_open_source_boundary_detects_missing_owner_and_readme_boundary(tmp_path: Path) -> None:
    _write(tmp_path / "SECURITY.md", "# Security\nGitHub Security Advisories\n")
    _write(
        tmp_path / "tests" / "data" / "README.md",
        "\n".join(
            [
                "# Test Data",
                "synthetic",
                "not exported from a live Apple Notes account",
                "verification inputs",
            ]
        ),
    )
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "\n".join(
            [
                "name: CI",
                "permissions:",
                "  contents: read",
                "jobs:",
                "  test:",
                "    steps:",
                "      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5",
                "      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            ]
        ),
    )
    _write(tmp_path / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml", "name: Bug report\n")
    _write(tmp_path / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml", "name: Feature request\n")
    _write(tmp_path / ".github" / "pull_request_template.md", "## Summary\n")

    errors = collect_open_source_boundary_errors(tmp_path)
    assert any("missing CODEOWNERS" in error for error in errors)
    assert any("missing README.md" in error for error in errors)


def test_open_source_boundary_detects_missing_history_boundary_tokens(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "git history",
                "forks",
                "secret scanning",
                "check_release_readiness.py",
            ]
        ),
    )
    _write(
        tmp_path / "SECURITY.md",
        "# Security\nGitHub Security Advisories\nsingle-maintainer owner\n",
    )
    _write(
        tmp_path / "tests" / "data" / "README.md",
        "\n".join(
            [
                "# Test Data",
                "synthetic",
                "not exported from a live Apple Notes account",
                "verification inputs",
            ]
        ),
    )
    _write(tmp_path / "CODEOWNERS", "* @owner\n")
    _write(tmp_path / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml", "name: Bug report\n")
    _write(tmp_path / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml", "name: Feature request\n")
    _write(tmp_path / ".github" / "pull_request_template.md", "## Summary\n")
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "\n".join(
            [
                "name: CI",
                "permissions:",
                "  contents: read",
                "jobs:",
                "  test:",
                "    steps:",
                "      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5",
                "      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            ]
        ),
    )
    _write(tmp_path / "scripts" / "ci" / "check_release_readiness.py", "print('ok')\n")

    errors = collect_open_source_boundary_errors(tmp_path)
    assert any("README.md is missing boundary token: pull request diffs" in error for error in errors)
    assert any("README.md is missing boundary token: branch protection" in error for error in errors)


def test_open_source_boundary_detects_missing_release_audit_script(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "git history",
                "pull request diffs",
                "forks",
                "mirrors",
                "downloaded clones",
                "branch protection",
                "secret scanning",
                "hosting settings",
                "required pull request reviews",
                "xiaojiou176",
                "opt-in integrations",
                "check_release_readiness.py",
            ]
        ),
    )
    _write(
        tmp_path / "SECURITY.md",
        "# Security\nGitHub Security Advisories\nsingle-maintainer owner\n",
    )
    _write(
        tmp_path / "tests" / "data" / "README.md",
        "\n".join(
            [
                "# Test Data",
                "synthetic",
                "not exported from a live Apple Notes account",
                "verification inputs",
            ]
        ),
    )
    _write(tmp_path / "CODEOWNERS", "* @owner\n")
    _write(tmp_path / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml", "name: Bug report\n")
    _write(tmp_path / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml", "name: Feature request\n")
    _write(tmp_path / ".github" / "pull_request_template.md", "## Summary\n")
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "\n".join(
            [
                "name: CI",
                "permissions:",
                "  contents: read",
                "jobs:",
                "  test:",
                "    steps:",
                "      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5",
                "      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            ]
        ),
    )

    errors = collect_open_source_boundary_errors(tmp_path)
    assert any("missing scripts/ci/check_release_readiness.py" in error for error in errors)


def test_optional_surface_contract_passes_for_aligned_surface(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "pip install -e .[ai]",
                "pip install -e .[mcp]",
                "pip install -e .[dashboard]",
                "pip install -e .[carve]",
                "`.[ai]`",
                "`.[mcp]`",
                "`dashboard`",
                "`carve`",
                "notes-recovery-mcp",
            ]
        ),
    )
    _write(
        tmp_path / "CONTRIBUTING.md",
        "\n".join(
            [
                "tests/test_ai_review.py",
                "tests/test_ask_case.py",
                "tests/test_mcp_server.py",
                "tests/test_dashboard_full.py",
                "tests/test_carve.py",
                "different transitive dependency sets",
                "one mixed environment",
                "stdio",
                "read-only / read-mostly",
                "case-root-centric",
                "ollama",
                "docker",
                "sqlite_dissect",
                "strings",
                "binwalk",
                "not part of the default baseline guarantee",
                "opt-in integrations",
            ]
        ),
    )

    assert collect_optional_surface_contract_errors(tmp_path) == []


def test_optional_surface_contract_detects_missing_contributing_tokens(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "`.[ai]`\n`.[mcp]`\n`dashboard`\n`carve`\npip install -e .[ai]\npip install -e .[mcp]\npip install -e .[dashboard]\nnotes-recovery-mcp\n",
    )
    _write(
        tmp_path / "CONTRIBUTING.md",
        "tests/test_dashboard_full.py\ntests/test_carve.py\ndifferent transitive dependency sets\none mixed environment\n",
    )

    errors = collect_optional_surface_contract_errors(tmp_path)
    assert any("CONTRIBUTING.md is missing optional-surface token" in error for error in errors)
