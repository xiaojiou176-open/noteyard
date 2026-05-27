from __future__ import annotations

ROOT_PUBLIC_CONTRACT_FILES = (
    "README.md",
    "proof.html",
    "llms.txt",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "SUPPORT.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".env.example",
)

README_PUBLIC_SURFACE_TOKENS = (
    "Noteyard",
    "notes-recovery",
    "proof.html",
    "llms.txt",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "SUPPORT.md",
    "AGENTS.md",
    "CLAUDE.md",
)

BASELINE_DOC_COMMAND = ".venv/bin/notes-recovery --help"
BASELINE_DEMO_COMMAND = ".venv/bin/notes-recovery demo"
FULL_SUITE_DOC_COMMAND = ".venv/bin/python -m pytest tests/ -q"
WORKFLOW_HELP_COMMAND = "notes-recovery --help"
WORKFLOW_DEMO_COMMAND = "notes-recovery demo"
DEEP_REALISM_JOB_NAME = "deep-realism"
PRE_PUSH_HOOK_ID = "baseline-smoke"
PRE_PUSH_STAGE_NAME = "pre-push"
PRE_PUSH_HELP_FRAGMENT = '--help >/dev/null'
PRE_PUSH_DEMO_FRAGMENT = 'demo > "$tmp"'

BASELINE_TESTS = (
    "tests/test_cli_entrypoints.py",
    "tests/test_public_demo_command.py",
    "tests/test_pipeline.py",
    "tests/test_case_contract.py",
    "tests/test_handlers_commands.py",
    "tests/test_auto_run_full.py",
    "tests/test_verify.py",
)

DEEP_REALISM_TESTS = (
    "tests/test_realistic_flow_e2e.py",
    "tests/test_timeline_integration.py",
    "tests/test_spotlight_deep.py",
    "tests/test_fts_index_build.py",
)

VERIFICATION_SUMMARY_TOKENS = (
    "baseline smoke",
    "full suite",
    "optional surfaces",
)

CONTRIBUTING_VERIFICATION_REQUIRED_TOKENS = (
    *VERIFICATION_SUMMARY_TOKENS,
    "deep realism",
    "required-check compatibility",
)

DISTRIBUTION_REQUIRED_TOKENS = (
    "copied-evidence workbench",
    "companion lanes around that workbench",
)

README_VERIFICATION_REQUIRED_TOKENS = (
    *VERIFICATION_SUMMARY_TOKENS,
    "CONTRIBUTING.md",
)

HOST_SAFETY_CHECK_TOKEN = "check_host_safety_contract.py"

HOST_SAFETY_DOC_TOKENS_BY_FILE = {
    "AGENTS.md": (
        "Host Safety Contract",
        "user-invoked previews",
    ),
    "README.md": (
        "Host Safety Boundary",
        "copied-evidence workbench",
    ),
    "CONTRIBUTING.md": (
        "Host Safety Contract",
        HOST_SAFETY_CHECK_TOKEN,
    ),
    "CLAUDE.md": (
        "Host Safety Contract",
    ),
    "SECURITY.md": (
        "Host-safety Boundary",
        "desktop automation",
    ),
}

RUNTIME_HYGIENE_TOKENS = (
    "relocation-safe at the repo level",
    "not environment-agnostic at the host level",
    "repository contract",
    "examples/ is intentionally excluded",
    "stable control surface",
    "runtime artifacts",
    "reserved, non-public staging area",
)

README_TAG_RELEASE_URL = (
    "https://github.com/xiaojiou176-open/noteyard/releases/tag/"
)

PUBLIC_STORY_FORBIDDEN_CHANGELOG_TOKENS = (
    "Static docs homepage",
    "Pages docs surface are now live",
    "docs/releases/",
    "Public visual asset set",
    "hero image",
    "case-flow image",
    "case-tree image",
    "report-sample image",
    "social-preview image",
    "demo GIF",
)

PUBLIC_STORY_FORBIDDEN_DOC_TOKENS = (
    "already exists on PyPI",
    "points at the live PyPI package",
    "Fresh PyPI read-back now confirms a live package at",
    "active official MCP Registry listing",
)
