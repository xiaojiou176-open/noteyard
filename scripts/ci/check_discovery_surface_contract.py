from __future__ import annotations

import sys
from pathlib import Path


DISCOVERY_FILES = (
    "llms.txt",
    "robots.txt",
    "sitemap.xml",
    "404.html",
    "site.webmanifest",
)

DISCOVERY_ASSET_FILES = (
    "assets/brand/noteyard-mark.svg",
    "assets/brand/favicon-32.png",
    "assets/brand/apple-touch-icon.png",
    "assets/brand/icon-192.png",
    "assets/brand/icon-512.png",
)

LLMS_REQUIRED_TOKENS = (
    "Noteyard",
    "notes-recovery",
    "notes-recovery-mcp",
    "Codex",
    "Claude Code",
    "MCP",
    "Not a primary front-door claim",
    "no shipped hosted API",
)

ROBOTS_REQUIRED_TOKENS = (
    "User-agent: *",
    "Allow: /",
    "Sitemap: https://xiaojiou176-open.github.io/noteyard/sitemap.xml",
)

SITEMAP_REQUIRED_TOKENS = (
    "https://xiaojiou176-open.github.io/noteyard/",
    "https://xiaojiou176-open.github.io/noteyard/llms.txt",
    "https://xiaojiou176-open.github.io/noteyard/robots.txt",
)

ERROR_PAGE_REQUIRED_TOKENS = (
    "Page not found",
    "Return to the landing page",
    "Open the GitHub repository",
    "Open the release feed",
)

WEBMANIFEST_REQUIRED_TOKENS = (
    '"name": "Noteyard"',
    '"short_name": "Noteyard"',
    '"start_url": "/noteyard/"',
    '"scope": "/noteyard/"',
    '"theme_color": "#16212b"',
    '"background_color": "#f5f1e8"',
    '"src": "assets/brand/icon-192.png"',
    '"src": "assets/brand/icon-512.png"',
)

README_DISCOVERY_TOKENS = (
    "[LLMs Guide](./llms.txt)",
    "Codex",
    "Claude Code",
    "good current examples of hosts",
    "remote-connector-first hosts",
    ".codex/config.toml",
    ".mcp.json",
)

INTEGRATIONS_DISCOVERY_TOKENS = (
    "llms.txt",
    ".venv/bin/python -m notes_recovery.mcp.server",
    "Codex / Claude Code",
    "good current examples of hosts",
    "remote-connector-first hosts",
    ".codex/config.toml",
    ".mcp.json",
    "[mcp_servers.noteyard]",
    "../.venv/bin/python",
    'cwd = ".."',
    "\"mcpServers\"",
)

LLMS_DISCOVERY_TOKENS = (
    "good current examples of hosts",
    ".codex/config.toml",
    ".mcp.json",
    "remote-connector-first hosts",
    "notes-recovery ai-review --demo",
    'notes-recovery ask-case --demo --question "What should I inspect first?"',
    ".venv/bin/python -m notes_recovery.mcp.server --case-dir ./output/Notes_Forensics_<run_ts>",
)

SUPPORT_DISCOVERY_TOKENS = (
    "which host you used",
    "Codex",
    "Claude Code",
    "OpenHands",
    "OpenCode",
    "another local runner",
)

INDEX_DISCOVERY_TOKENS = (
    "Follow the 4-command proof path",
    "See the public proof boundary",
    "4 operator-first steps in under 5 minutes",
    "One case, three consumers",
    "Public proof boundary",
    "LLMs guide",
    "Builder path: Codex and Claude Code",
    "Registration command:",
    "twitter:title",
    "canonical",
    "og:site_name",
    "og:locale",
    'rel="icon"',
    'apple-touch-icon',
    'site.webmanifest',
    'brand-mark',
    'hreflang="x-default"',
    '"inLanguage": "en-US"',
    "Comparison path only.",
    ".codex/config.toml",
    ".mcp.json",
    "../.venv/bin/python",
    'cwd = ".."',
)


def _read(repo_root: Path, rel_path: str) -> str:
    path = repo_root / rel_path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def collect_discovery_surface_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    for rel_path in DISCOVERY_FILES:
        if not (repo_root / rel_path).exists():
            errors.append(f"missing discovery surface file: {rel_path}")

    for rel_path in DISCOVERY_ASSET_FILES:
        if not (repo_root / rel_path).exists():
            errors.append(f"missing discovery asset file: {rel_path}")

    llms_text = _read(repo_root, "llms.txt")
    if not llms_text:
        errors.append("missing llms.txt")
    else:
        for token in LLMS_REQUIRED_TOKENS:
            if token not in llms_text:
                errors.append(f"llms.txt is missing required token: {token}")
        for token in LLMS_DISCOVERY_TOKENS:
            if token not in llms_text:
                errors.append(f"llms.txt is missing discovery token: {token}")

    robots_text = _read(repo_root, "robots.txt")
    if not robots_text:
        errors.append("missing robots.txt")
    else:
        for token in ROBOTS_REQUIRED_TOKENS:
            if token not in robots_text:
                errors.append(f"robots.txt is missing required token: {token}")

    sitemap_text = _read(repo_root, "sitemap.xml")
    if not sitemap_text:
        errors.append("missing sitemap.xml")
    else:
        for token in SITEMAP_REQUIRED_TOKENS:
            if token not in sitemap_text:
                errors.append(f"sitemap.xml is missing required token: {token}")

    error_page_text = _read(repo_root, "404.html")
    if not error_page_text:
        errors.append("missing 404.html")
    else:
        for token in ERROR_PAGE_REQUIRED_TOKENS:
            if token not in error_page_text:
                errors.append(f"404.html is missing required token: {token}")

    webmanifest_text = _read(repo_root, "site.webmanifest")
    if not webmanifest_text:
        errors.append("missing site.webmanifest")
    else:
        for token in WEBMANIFEST_REQUIRED_TOKENS:
            if token not in webmanifest_text:
                errors.append(f"site.webmanifest is missing required token: {token}")

    readme_text = _read(repo_root, "README.md")
    if not readme_text:
        errors.append("missing README.md")
    else:
        for token in README_DISCOVERY_TOKENS:
            if token not in readme_text:
                errors.append(f"README.md is missing discovery token: {token}")

    integrations_text = _read(repo_root, "INTEGRATIONS.md")
    if not integrations_text:
        errors.append("missing INTEGRATIONS.md")
    else:
        for token in INTEGRATIONS_DISCOVERY_TOKENS:
            if token not in integrations_text:
                errors.append(f"INTEGRATIONS.md is missing discovery token: {token}")

    support_text = _read(repo_root, "SUPPORT.md")
    if not support_text:
        errors.append("missing SUPPORT.md")
    else:
        for token in SUPPORT_DISCOVERY_TOKENS:
            if token not in support_text:
                errors.append(f"SUPPORT.md is missing discovery token: {token}")

    index_text = _read(repo_root, "index.html")
    if not index_text:
        errors.append("missing index.html")
    else:
        for token in INDEX_DISCOVERY_TOKENS:
            if token not in index_text:
                errors.append(f"index.html is missing discovery token: {token}")

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors = collect_discovery_surface_errors(repo_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("discovery surface contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
