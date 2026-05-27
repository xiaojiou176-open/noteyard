from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    from scripts.ci.contracts import (
        BASELINE_DEMO_COMMAND,
        BASELINE_DOC_COMMAND,
        BASELINE_TESTS,
        CONTRIBUTING_VERIFICATION_REQUIRED_TOKENS,
        DEEP_REALISM_JOB_NAME,
        DEEP_REALISM_TESTS,
        DISTRIBUTION_REQUIRED_TOKENS,
        FULL_SUITE_DOC_COMMAND,
        PRE_PUSH_DEMO_FRAGMENT,
        PRE_PUSH_HELP_FRAGMENT,
        PRE_PUSH_HOOK_ID,
        PRE_PUSH_STAGE_NAME,
        README_VERIFICATION_REQUIRED_TOKENS,
        WORKFLOW_DEMO_COMMAND,
        WORKFLOW_HELP_COMMAND,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from contracts import (
        BASELINE_DEMO_COMMAND,
        BASELINE_DOC_COMMAND,
        BASELINE_TESTS,
        CONTRIBUTING_VERIFICATION_REQUIRED_TOKENS,
        DEEP_REALISM_JOB_NAME,
        DEEP_REALISM_TESTS,
        DISTRIBUTION_REQUIRED_TOKENS,
        FULL_SUITE_DOC_COMMAND,
        PRE_PUSH_DEMO_FRAGMENT,
        PRE_PUSH_HELP_FRAGMENT,
        PRE_PUSH_HOOK_ID,
        PRE_PUSH_STAGE_NAME,
        README_VERIFICATION_REQUIRED_TOKENS,
        WORKFLOW_DEMO_COMMAND,
        WORKFLOW_HELP_COMMAND,
    )


DOC_FILES = (
    "README.md",
    "CONTRIBUTING.md",
    "DISTRIBUTION.md",
)

FORBIDDEN_BASELINE_LINES = (
    ".venv/bin/python -m pytest tests/",
    "python -m pytest tests/",
)


def _extract_job_block(workflow_text: str, job_name: str) -> str | None:
    match = re.search(
        rf"(?ms)^  {re.escape(job_name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        workflow_text,
    )
    if match is None:
        return None
    return match.group(0)


def _extract_precommit_hook_block(config_text: str, hook_id: str) -> str | None:
    match = re.search(
        rf"(?ms)^      - id: {re.escape(hook_id)}\n(.*?)(?=^      - id: |\Z)",
        config_text,
    )
    if match is None:
        return None
    return match.group(0)


def _read(repo_root: Path, rel_path: str) -> str | None:
    path = repo_root / rel_path
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def collect_verification_contract_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    workflow_text = _read(repo_root, ".github/workflows/ci.yml")
    if workflow_text is None:
        return ["missing .github/workflows/ci.yml"]

    baseline_block = _extract_job_block(workflow_text, "baseline")
    if baseline_block is None:
        errors.append("workflow is missing the baseline job block")
        baseline_block = workflow_text

    if WORKFLOW_HELP_COMMAND not in baseline_block:
        errors.append("workflow baseline is missing the CLI help command")
    if WORKFLOW_DEMO_COMMAND not in baseline_block:
        errors.append("workflow baseline is missing the public demo command")

    for test_path in BASELINE_TESTS:
        if test_path not in baseline_block:
            errors.append(f"workflow baseline is missing canonical smoke test: {test_path}")

    for test_path in DEEP_REALISM_TESTS:
        if test_path in baseline_block:
            errors.append(
                f"workflow baseline must not include deep realism test: {test_path}"
            )

    deep_realism_block = _extract_job_block(workflow_text, DEEP_REALISM_JOB_NAME)
    if deep_realism_block is None:
        errors.append(
            f"workflow is missing the `{DEEP_REALISM_JOB_NAME}` job for deeper-path verification"
        )
    else:
        for test_path in DEEP_REALISM_TESTS:
            if test_path not in deep_realism_block:
                errors.append(
                    f"`{DEEP_REALISM_JOB_NAME}` is missing deep realism test: {test_path}"
                )

    for trigger in ("schedule:", "workflow_dispatch:"):
        if trigger not in workflow_text:
            errors.append(
                f"workflow must expose `{DEEP_REALISM_JOB_NAME}` through `{trigger}`"
            )

    precommit_text = _read(repo_root, ".pre-commit-config.yaml")
    if precommit_text is None:
        errors.append("missing local verification contract file: .pre-commit-config.yaml")
    else:
        prepush_block = _extract_precommit_hook_block(precommit_text, PRE_PUSH_HOOK_ID)
        if prepush_block is None:
            errors.append(
                f".pre-commit-config.yaml is missing the `{PRE_PUSH_HOOK_ID}` pre-push hook"
            )
        else:
            if PRE_PUSH_HELP_FRAGMENT not in prepush_block:
                errors.append(
                    f"`{PRE_PUSH_HOOK_ID}` is missing the CLI help smoke fragment"
                )
            if PRE_PUSH_DEMO_FRAGMENT not in prepush_block:
                errors.append(
                    f"`{PRE_PUSH_HOOK_ID}` is missing the public demo smoke fragment"
                )
            if PRE_PUSH_STAGE_NAME not in prepush_block:
                errors.append(
                    f"`{PRE_PUSH_HOOK_ID}` must stay scoped to the `{PRE_PUSH_STAGE_NAME}` stage"
                )
            for test_path in BASELINE_TESTS:
                if test_path not in prepush_block:
                    errors.append(
                        f"`{PRE_PUSH_HOOK_ID}` is missing canonical smoke test: {test_path}"
                    )
            for test_path in DEEP_REALISM_TESTS:
                if test_path in prepush_block:
                    errors.append(
                        f"`{PRE_PUSH_HOOK_ID}` must not include deep realism test: {test_path}"
                    )

    readme_text = _read(repo_root, "README.md")
    if readme_text is None:
        errors.append("missing verification contract doc: README.md")
    else:
        lowered = readme_text.casefold()
        stripped_lines = {line.strip() for line in readme_text.splitlines()}
        for token in README_VERIFICATION_REQUIRED_TOKENS:
            if token.casefold() not in lowered:
                errors.append(f"README.md is missing verification contract token: {token}")
        for forbidden in FORBIDDEN_BASELINE_LINES:
            if forbidden in stripped_lines:
                errors.append(f"README.md must not claim `{forbidden}` as the baseline contract")
        for test_path in BASELINE_TESTS:
            if test_path in readme_text:
                errors.append(f"README.md must keep canonical smoke test paths in CONTRIBUTING.md only: {test_path}")

    contributing_text = _read(repo_root, "CONTRIBUTING.md")
    if contributing_text is None:
        errors.append("missing verification contract doc: CONTRIBUTING.md")
    else:
        lowered = contributing_text.casefold()
        stripped_lines = {line.strip() for line in contributing_text.splitlines()}

        if BASELINE_DOC_COMMAND not in contributing_text:
            errors.append("CONTRIBUTING.md is missing the canonical baseline help command")
        if BASELINE_DEMO_COMMAND not in contributing_text:
            errors.append("CONTRIBUTING.md is missing the canonical public demo command")

        for forbidden in FORBIDDEN_BASELINE_LINES:
            if forbidden in stripped_lines:
                errors.append(f"CONTRIBUTING.md must not claim `{forbidden}` as the baseline contract")

        for token in CONTRIBUTING_VERIFICATION_REQUIRED_TOKENS:
            if token not in lowered:
                errors.append(f"CONTRIBUTING.md is missing verification contract token: {token}")

        for test_path in BASELINE_TESTS:
            if test_path not in contributing_text:
                errors.append(f"CONTRIBUTING.md is missing canonical smoke test: {test_path}")
        for test_path in DEEP_REALISM_TESTS:
            if test_path not in contributing_text:
                errors.append(f"CONTRIBUTING.md is missing deep realism test: {test_path}")
        if FULL_SUITE_DOC_COMMAND not in contributing_text:
            errors.append("CONTRIBUTING.md should document the broader full suite sweep explicitly")

    distribution_text = _read(repo_root, "DISTRIBUTION.md")
    if distribution_text is None:
        errors.append("missing verification contract doc: DISTRIBUTION.md")
    else:
        lowered = distribution_text.casefold()
        for token in DISTRIBUTION_REQUIRED_TOKENS:
            if token.casefold() not in lowered:
                errors.append(f"DISTRIBUTION.md is missing distribution boundary token: {token}")

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors = collect_verification_contract_errors(repo_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("verification contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
