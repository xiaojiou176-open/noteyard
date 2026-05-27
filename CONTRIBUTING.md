# Contributing

## Development Setup

Create a virtual environment and install the repository in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
```

If you need to reclaim local disk, `.venv/` is a safe rebuildable surface:

```bash
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
```

That cleanup path only applies to the local developer environment. It does not
change the copied-evidence workflow or any tracked/public proof surface.

Install the local guardrail binaries used by repository hooks:

```bash
brew install gitleaks git-secrets actionlint
pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push
```

Pin a privacy-preserving repository-local Git identity for this repository:

```bash
git config --local user.name "<your-github-handle>"
git config --local user.email "<your-github-handle>@users.noreply.github.com"
```

This repository expects contributor commits to use:

- a stable non-empty display name
- a GitHub `@users.noreply.github.com` email
- no AI assistant or generic bot persona as the human author identity

The history gate still tolerates GitHub's platform-side
`GitHub <noreply@github.com>` committer on synthetic PR merge refs or hosted
merge flows, and keeps `dependabot[bot]` as the only bot author exception.

If you are not on macOS, install equivalent `gitleaks` and `git-secrets`
binaries with your platform package manager before running `pre-commit`.

The local guardrail chain now also runs
`python3 scripts/ci/check_sensitive_surface.py` to block tracked/public-surface
regressions such as secrets, personal GitHub noreply identities, absolute
path-like strings, logs, and other sensitive artifacts before they land in the
repository.

The pre-push and CI guardrail chain also runs
`python3 scripts/ci/check_github_security_alerts.py` so GitHub
secret-scanning open alerts and GitHub code-scanning open alerts must stay at
zero before the repository can claim a clean public security surface.

GitHub PR dependency review is also backed by a repo-owned dependency snapshot
lane because this repository ships a PEP 621 `pyproject.toml` contract instead
of a static lockfile-only layout. The snapshot lane installs the full validation
environment and submits the resolved Python package set to GitHub's dependency
graph so pull-request dependency review can diff real package state instead of
failing as "unsupported."

If you need to inspect the payload locally before wiring a workflow change, run:

```bash
python3 scripts/ci/submit_dependency_snapshot.py --repo xiaojiou176-open/noteyard --dry-run
```

For a maintainer-side full-history secret scan beyond the default local hooks,
run:

```bash
trufflehog git "file://$PWD" --no-update --json --fail --results=verified,unknown,unverified
```

Install optional extras only when you are working on those surfaces:

```bash
python -m pip install -e .[ai]
python -m pip install -e .[mcp]
python -m pip install -e .[dashboard]
python -m pip install -e .[carve]
```

If you are validating the optional plugin surface itself, use the contract
checker before you trust any external-tool config:

```bash
.venv/bin/notes-recovery plugins-validate --config ./plugins.json
```

## Local Rebuildable Maintenance

`.venv/` is the canonical repo-local Python environment for contributor flows.

Treat it as:

- rebuildable
- local-only
- safe to delete when you explicitly want to recreate the toolchain

Rebuild path:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
```

This repository does not yet ship a dedicated `.venv` cleanup command, so the
current contract is "manual-but-safe rebuildable surface", not "never touch".

If you are touching the public README or demo narrative, start with the
zero-risk public tour:

```bash
notes-recovery demo
```

If you are validating the Wave 1 operator path, run the front-door preflight as
well:

```bash
.venv/bin/notes-recovery doctor
```

Treat `doctor` as an operator-facing readiness check, not as the baseline smoke
contract. It should help you decide whether this host is ready for the standard
copied-evidence workflow, whether you should stay on `demo`, or whether you
only need optional extras.

If you are touching the AI review surface, start with the synthetic proof path:

```bash
.venv/bin/notes-recovery ai-review --demo
```

That command is designed to stay on tracked synthetic review artifacts. The
real-case AI path must continue to read derived outputs first and must not
default to uploading raw copied evidence.

If you are touching the protocol surface, keep it local and case-root-centric:

```bash
.venv/bin/notes-recovery-mcp --case-dir ./output/Notes_Forensics_<run_ts>
```

Round 4 starts with `stdio` transport and a read-only / read-mostly contract.
It should help external agents consume derived case artifacts without turning
the repo into a broad host-control server.

If you are touching public distribution artifacts, rebuild the distribution
bundles locally:

```bash
.venv/bin/python scripts/release/build_distribution_bundles.py --out-dir ./dist
```

If you are touching `server.json` or the MCP Registry story, keep the package
boundary honest: registry metadata alone is not an MCP Registry listing claim.
The current repo contract still targets
`noteyard==0.1.0.post1` on the PyPI lane, but live package state
can drift outside the repository. Keep the package name/version in
`server.json` aligned with the current repo version, and refresh PyPI
read-back before you repeat any live-package claim.

PyPI metadata/build-readiness smoke:

```bash
.venv/bin/python scripts/release/check_pypi_publish_readiness.py
```

Current PyPI install smoke:

```bash
python -m pip install noteyard==0.1.0.post1
```

Independent skill publish-readiness smoke:

```bash
.venv/bin/python scripts/release/check_skill_publish_readiness.py
```

Docker metadata/build-readiness smoke:

```bash
.venv/bin/python scripts/release/check_docker_surface.py --metadata-only
```

Treat the root-level contract files as the only tracked public documentation
surface. If you change the repository contract, update the relevant root files
instead of introducing a parallel docs tree.

## Host Safety Contract

This repository is allowed to inspect copied Apple Notes evidence on macOS.
It is not allowed to manage the host desktop.

Do not introduce:

- `killall`, `pkill`, `kill -9`, `os.kill(...)`, `process.kill(...)`, or any
  broad signal helper
- `osascript`, `System Events`, `AppleEvent`, `loginwindow`, Force Quit flows,
  or desktop-wide GUI automation
- "clean up the host first" routines that target shared browsers, Notes,
  Docker, Finder, or unrelated processes

The allowed scope remains:

- copied evidence inside case roots
- repo-local rebuildable surfaces such as `.venv/` and `.runtime-cache/`
- explicit user-invoked previews of repo-owned output paths

Before landing host-adjacent changes, run:

```bash
python3 scripts/ci/check_host_safety_contract.py
```

## Canonical Local Checks

This file is the canonical detailed verification contract. Keep README focused
on the public front door, and keep the full command-level verification surface
here.

## CI Layer Map

Use this layer map when you decide where a check belongs:

| Layer | Default trigger | What belongs here |
| --- | --- | --- |
| `pre-commit` | every local commit attempt | fast local static gates, hygiene, docs/public-surface drift guards, and host-safety checks |
| `pre-push` | before pushing a branch | local baseline smoke on the core recovery path, plus commit-history identity checks |
| `hosted` | GitHub Actions on `push` / `pull_request` | required matrix jobs, repo-hygiene/security scans, optional-surface smoke, and deterministic distribution build-readiness |
| `nightly` | scheduled GitHub Actions and manual dispatch | non-required deep analysis that is useful over time but too heavy or too platform-bound for the default pull-request fast lane |
| `manual` | maintainer-triggered or owner-side | live GitHub settings/storefront checks, registry/marketplace submission, PyPI publish, and final release-readiness acceptance |

Keep remote GitHub-state checks and publication checks out of the default local
push path unless they are the specific surface you are actively validating.

Start with the baseline smoke contract:

```bash
.venv/bin/notes-recovery --help >/dev/null
tmp=$(mktemp)
.venv/bin/notes-recovery demo > "$tmp"
test -s "$tmp"
grep -q "Noteyard public demo" "$tmp"
.venv/bin/python -m pytest \
  tests/test_cli_entrypoints.py \
  tests/test_public_demo_command.py \
  tests/test_pipeline.py \
  tests/test_case_contract.py \
  tests/test_handlers_commands.py \
  tests/test_auto_run_full.py \
  tests/test_verify.py \
  -q
```

That baseline contract is intentionally narrow:

- `notes-recovery --help` proves the installed CLI entrypoint resolves
- `notes-recovery demo` proves the public-safe first-look path is non-empty
- the canonical smoke test list proves the core `.[dev]` pipeline still holds

Treat the `baseline` job name as the merge-critical first-success lane. It is
the fast PR gate, not the place for longer realism or indexing checks.

The workflow also keeps a dedicated **deep realism** lane for the slower paths
that still matter after merge:

- it runs on pushes to `main`
- it is available through scheduled/nightly automation
- it is available through manual dispatch when you want the deeper path on demand

The workflow keeps the existing required-check names stable for branch-protection
compatibility. Jobs such as `extras-dashboard` remain separate compatibility
contexts; they do not redefine what the baseline contract means.

Deep realism smoke:

```bash
.venv/bin/python -m pytest \
  tests/test_realistic_flow_e2e.py \
  tests/test_timeline_integration.py \
  tests/test_spotlight_deep.py \
  tests/test_fts_index_build.py \
  -q
```

Run optional smoke checks only when you touch those areas.

AI review smoke:

```bash
python -m pip install -e .[dev,ai]
.venv/bin/python -m pytest \
  tests/test_ai_review.py \
  tests/test_ask_case.py \
  -q
```

Case-diff smoke:

```bash
.venv/bin/python -m pytest \
  tests/test_case_diff.py \
  -q
```

MCP smoke:

```bash
python -m pip install -e .[dev,mcp]
.venv/bin/python -m pytest \
  tests/test_mcp_server.py \
  -q
```

Dashboard smoke:

```bash
python -m pip install -e .[dev,dashboard]
.venv/bin/python -m pytest \
  tests/test_apps_entrypoints.py \
  tests/test_dashboard_full.py \
  -q
```

Distribution bundle smoke:

```bash
.venv/bin/python -m pytest \
  tests/test_distribution_bundles.py \
  -q
.venv/bin/python scripts/release/build_distribution_bundles.py --out-dir ./dist
```

PyPI metadata/build-readiness smoke:

```bash
.venv/bin/python scripts/release/check_pypi_publish_readiness.py
```

Carve smoke:

```bash
python -m pip install -e .[dev,carve]
.venv/bin/python -m pytest \
  tests/test_carve.py \
  -q
```

Optional surfaces intentionally use different transitive dependency sets. Do
not assume one mixed environment is the canonical developer contract.

AI provider notes:

- `mock` is reserved for the synthetic demo/testing path
- `ollama` is the local-first real provider path in the current wave
- `openai` is cloud-backed and requires explicit opt-in via `--allow-cloud` or `NOTES_AI_ALLOW_CLOUD`
- `.[ai]` installs the local Ollama HTTP client dependency used by the current wave
- do not treat AI output as forensic ground truth

MCP protocol notes:

- `.[mcp]` installs the local MCP SDK used by the current wave
- `notes-recovery-mcp` uses local `stdio` transport first
- the MCP server is read-only / read-mostly and case-root-centric by default
- it must not expose the live Notes store or broad filesystem control as a default surface

Plugin contract notes:

- the plugin surface remains local and optional
- `notes-recovery plugins-validate --config <plugins.json>` is the contract-checking entrypoint
- plugin commands must stay on direct tool binaries; shell trampolines, host-control executables, and desktop automation helpers are rejected
- keep plugin output directories relative to the case root
- treat placeholder or unavailable tools as validation warnings/errors, not as silent success

## Local Runtime Hygiene

The local runtime boundary is intentionally small:

- `.venv/` is the canonical repo-local Python environment.
- `.venv/` is **rebuildable** and may be removed when you explicitly want a
  clean local toolchain.
- `.runtime-cache/` is local support state only. It can hold temporary scans or
  draft outputs, but it is never copied-evidence truth.

Safe reset path:

```bash
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
```

Do not treat copied Notes evidence, case-root outputs, or public-safe export
bundles as runtime-cleanup targets. Runtime hygiene here only applies to
rebuildable local support surfaces.

For repo-owned release/rewrite support residue under `.runtime-cache/`, use the
maintainer-only cleanup helper:

```bash
python scripts/ops/clean_support_state.py --dry-run
python scripts/ops/clean_support_state.py --apply
```

That helper is intentionally narrow. It may remove:

- `.runtime-cache/pypi-release`
- `.runtime-cache/history-rewrite-*`
- `.runtime-cache/release`
- `.runtime-cache/pypi-publish-attempt-*`
- `.runtime-cache/lighthouse-pages*`
- `.runtime-cache/security-audit`
- `.runtime-cache/temp`
- `.runtime-cache/dist-bundles`
- `.runtime-cache/*starter*.zip`
- `.runtime-cache/verify-*`
- `.runtime-cache/gitleaks-*.json`

It does **not** touch copied evidence, `output/`, Docker state, browser
profiles, or shared machine caches.

For deeper changes, run the broader full suite engineering sweep:

```bash
.venv/bin/python -m pytest tests/ -q
```

That full suite command is useful engineering signal, but it is not the
default baseline CI guarantee.

## Public-Safe Export Contract

Use `notes-recovery public-safe-export` when you need a reviewable bundle that
is safer to share outside the local forensic environment.

```bash
notes-recovery public-safe-export \
  --dir ./output/Notes_Forensics_<run_ts> \
  --out ./output/public_safe_bundle
```

Rules:

- treat the original case root as forensic-local ground truth
- treat the public-safe export as a redacted sharing bundle, not a replayable case
- do not publish raw `DB_Backup/`, `Recovered_DB/`, `Recovered_Blobs/`, or
  plugin raw outputs as public proof
- use the synthetic demo or a `public-safe-export` bundle for release-facing
  screenshots, examples, or operator-facing walkthroughs

## Case Root Contract

Treat the timestamped case root as the canonical workflow container. The
stable top-level surface is owned by `notes_recovery.case_contract` and is the
single source of truth for directory names, manifest filenames, and prefix
matching used by services, scans, exports, and tests.

### Primary evidence surfaces

| Surface | Role |
| --- | --- |
| `DB_Backup/` | copied Notes group container, including `NoteStore.sqlite` and WAL/SHM files |
| `Cache_Backup/` | optional copied Notes cache evidence |
| `Spotlight_Backup/` | optional copied CoreSpotlight evidence |

### Derived analysis surfaces

| Surface / Prefix | Role |
| --- | --- |
| `Recovered_DB/` | sqlite recovery outputs |
| `Recovered_Blobs*/` | carved payload outputs and recovered variants |
| `Recovered_Notes*/` | stitched note reconstructions |
| `Query_Output*/` | query CSV outputs and recovered-query variants |
| `Protobuf_Output*/` | parsed protobuf outputs |
| `Verification_*/` | verification previews and hit tables |
| `AI_Review*/` | AI-assisted triage, findings, and next-step guidance |
| `Spotlight_Analysis*/` | deep Spotlight analysis outputs |
| `Timeline*/` | timeline reports and event exports |
| `Plugins_Output/` | external-tool results |
| `Text_Bundle*/` | review-friendly text copies and inventories |

### Case manifests and summaries

| File | Role |
| --- | --- |
| `run_manifest_<run_ts>.json` | machine-readable per-run stage ledger |
| `case_manifest_<run_ts>.json` | case-level output inventory and hash/signature pointers |
| `Meta/pipeline_summary_<run_ts>.md` | human-readable stage summary |

Rules:

- Treat `DB_Backup/`, `Cache_Backup/`, and `Spotlight_Backup/` as forensic-local ground truth inside a case.
- Treat everything else as derived or presentation-layer output unless a service explicitly documents otherwise.
- Reuse the shared contract constants instead of open-coding path strings in new services or tests.
- When adding a new top-level case surface, update `notes_recovery.case_contract`, the relevant tests, and this section in the same change.

## Policy And Release Checks

Repository policy checks:

```bash
.venv/bin/python scripts/ci/check_docs_surface.py
.venv/bin/python scripts/ci/check_verification_contract.py
.venv/bin/python scripts/ci/check_optional_surface_contract.py
.venv/bin/python scripts/ci/check_public_story_truth.py
.venv/bin/python scripts/ci/check_repo_hygiene.py --mode hygiene
.venv/bin/python scripts/ci/check_repo_hygiene.py --mode open-source-boundary
.venv/bin/python scripts/ci/check_commit_identity.py --mode all
.venv/bin/python scripts/ci/check_runtime_hygiene.py
.venv/bin/python scripts/ci/check_english_surface.py
.venv/bin/python scripts/ci/check_public_safe_outputs.py
pre-commit run --all-files
```

Release-readiness audit:

```bash
.venv/bin/python scripts/ci/check_release_readiness.py \
  --repo xiaojiou176-open/noteyard \
  --strict
```

Treat `check_release_readiness.py` as the one-command audit for current GitHub
hosting state. It covers git history, pull request diffs, forks, mirrors or
downloaded-clone risk proxies, branch protection, required pull request
reviews, secret scanning, and GitHub Security Advisories reachability.

The current deterministic required checks on `main` are the branch-protection
contexts exposed by the canonical GitHub repository:

- `baseline`
- `extras-ai-mcp`
- `extras-dashboard`
- `extras-carve-protobuf`
- `repo-hygiene`
- `local-guardrails`
- `open-source-boundary`

Only `baseline` is the merge-critical first-success lane. The remaining
required-check compatibility contexts stay split so the repository can keep the
current GitHub branch-protection names stable without pretending optional
surfaces are part of the baseline smoke contract.

CodeQL is still part of the repository's security posture, but it remains a
non-required analysis lane in the current branch-protection contract. Keep it
SHA-pinned and visible on pushes and pull requests, but do not treat it as the
default merge gate unless the maintainers explicitly tighten that policy later.

## GitHub Settings Checklist

These checks live partly outside the tracked tree, so keep them in a maintainer
checklist instead of pretending they are repo-side facts:

- Verify that the current Topics list still matches the repository positioning
- Upload and re-check the custom social preview from the GitHub repository
  Settings UI after any `assets/social/` change. Treat REST
  `open_graph_image_url` as the custom-upload signal; the GraphQL
  `openGraphImageUrl` field can still expose a generated repository card.
- Confirm that the current release page includes the expected synthetic public
  demo asset before describing it as live

When you change release-facing or storefront-facing claims, verify the live
GitHub state first instead of trusting a local branch snapshot from memory.
Treat the canonical public truth as:

- the live `main` branch on GitHub
- the live GitHub Releases page
- the current GitHub repository settings and branch protection state

If repo-side docs disagree with the live GitHub state, update the docs in the
same change that resolves the drift. Do not leave stale release or storefront
claims behind for a later cleanup.

Lower-level release drills may still be useful:

```bash
"$HOME/.cache/codex_scans/scancode-py313/bin/scancode" \
  --license \
  --copyright \
  --classify \
  --summary \
  --strip-root \
  --ignore '.git*' \
  --ignore '.venv*' \
  --ignore '.pytest_cache*' \
  --ignore '.runtime-cache*' \
  --ignore '.cache*' \
  --ignore 'cache*' \
  --ignore 'logs*' \
  --ignore 'log*' \
  --ignore 'output*' \
  --ignore 'examples*' \
  --json-pp .runtime-cache/scancode/repo-scan.json \
  .
gh api 'repos/xiaojiou176-open/noteyard'
gh api 'repos/xiaojiou176-open/noteyard/branches/main/protection'
gh api 'repos/xiaojiou176-open/noteyard/secret-scanning/alerts?per_page=100'
gh api 'repos/xiaojiou176-open/noteyard/security-advisories?state=all'
```

## Optional Surface Boundary

The optional surface contract is intentionally narrow:

- `dashboard` and `carve` are opt-in capability areas
- `mcp` is an opt-in protocol surface
- `docker`, `sqlite_dissect`, `strings`, and `binwalk` are optional local tool
  integrations
- those tools and extras are not part of the default baseline guarantee
- treat them as opt-in integrations instead of part of the default baseline

If you add a new optional surface, add a smoke gate for it instead of silently
expanding the baseline job.

## Guidelines

- Work only on copies of Apple Notes data, never on the live original store.
- Keep changes surgical and evidence-based.
- Update `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`,
  `AGENTS.md`, or `CLAUDE.md` when the public contract changes.
- Avoid committing local artifacts, logs, recovered data, or AI work
  directories.
- Keep `.env.example` aligned with any documented environment inputs.

## Pull Requests

- Explain the user-facing or repo-policy change.
- List the exact verification commands you ran.
- Call out validation gaps or environment-specific assumptions.
- Keep unrelated refactors out of the same PR.
