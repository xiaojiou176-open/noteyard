from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

try:
    from scripts.ci.contracts import (
        HOST_SAFETY_CHECK_TOKEN,
        HOST_SAFETY_DOC_TOKENS_BY_FILE,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from contracts import (
        HOST_SAFETY_CHECK_TOKEN,
        HOST_SAFETY_DOC_TOKENS_BY_FILE,
    )


SCAN_ROOTS = (
    "notes_recovery",
    "scripts",
    "tests",
    ".github",
)

ROOT_SCAN_FILES = (
    ".pre-commit-config.yaml",
)

SCANNED_SUFFIXES = {
    ".py",
    ".sh",
    ".bash",
    ".zsh",
    ".command",
    ".yml",
    ".yaml",
    ".toml",
}

SELF_AUDIT_IGNORED_PATHS = {
    "scripts/ci/check_host_safety_contract.py",
    "tests/test_host_safety_contract.py",
}

FORBIDDEN_HOST_CONTROL_PATTERNS = (
    ("killall", re.compile(r"\bkillall\b", re.IGNORECASE)),
    ("pkill", re.compile(r"\bpkill\b", re.IGNORECASE)),
    ("kill -9", re.compile(r"(?<![A-Za-z0-9_])kill\s+-9\b", re.IGNORECASE)),
    ("os.kill(...)", re.compile(r"\bos\.kill\s*\(", re.IGNORECASE)),
    ("process.kill(...)", re.compile(r"\bprocess\.kill\s*\(", re.IGNORECASE)),
    ("osascript", re.compile(r"\bosascript\b", re.IGNORECASE)),
    ("System Events", re.compile(r"System Events", re.IGNORECASE)),
    ("AppleEvent", re.compile(r"\bAppleEvent\b", re.IGNORECASE)),
    ("loginwindow", re.compile(r"\bloginwindow\b", re.IGNORECASE)),
    ("showForceQuitPanel", re.compile(r"\bshowForceQuitPanel\b", re.IGNORECASE)),
)


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _should_scan(path: Path) -> bool:
    return path.suffix in SCANNED_SUFFIXES


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
        return node.attr
    return None


def _extract_constant_command_text(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first_arg = node.args[0]
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        return first_arg.value
    if isinstance(first_arg, (ast.List, ast.Tuple)):
        parts: list[str] = []
        for item in first_arg.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                return None
            parts.append(item.value)
        return " ".join(parts)
    return None


def _command_text_host_safety_issue(command_text: str) -> str | None:
    for label, pattern in FORBIDDEN_HOST_CONTROL_PATTERNS:
        if pattern.search(command_text):
            return label
    return None


def _scan_python_file(path: Path, relative_path: str, text: str) -> list[str]:
    errors: list[str] = []

    try:
        tree = ast.parse(text, filename=relative_path)
    except SyntaxError as exc:
        line_number = exc.lineno or 1
        return [
            (
                f"{relative_path}:{line_number} could not be parsed for host-safety scanning: "
                f"{exc.msg}"
            )
        ]

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node.func)
        if call_name == "os.kill":
            errors.append(
                f"{relative_path}:{node.lineno} contains forbidden host-control primitive: os.kill(...)"
            )
            continue
        if call_name == "process.kill":
            errors.append(
                f"{relative_path}:{node.lineno} contains forbidden host-control primitive: process.kill(...)"
            )
            continue

        if call_name in {"os.system", "os.popen"}:
            command_text = _extract_constant_command_text(node)
            if not command_text:
                continue
            issue = _command_text_host_safety_issue(command_text)
            if issue:
                errors.append(
                    f"{relative_path}:{node.lineno} contains forbidden host-control primitive: {issue}"
                )
            continue

        if call_name in {
            "subprocess.Popen",
            "subprocess.call",
            "subprocess.check_call",
            "subprocess.check_output",
            "subprocess.run",
        }:
            command_text = _extract_constant_command_text(node)
            if command_text:
                issue = _command_text_host_safety_issue(command_text)
                if issue:
                    errors.append(
                        f"{relative_path}:{node.lineno} contains forbidden host-control primitive: {issue}"
                    )

            continue

    return errors


def _scan_text_file(relative_path: str, text: str) -> list[str]:
    errors: list[str] = []
    for label, pattern in FORBIDDEN_HOST_CONTROL_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        line_number = text.count("\n", 0, match.start()) + 1
        errors.append(
            f"{relative_path}:{line_number} contains forbidden host-control primitive: {label}"
        )
    return errors


def _iter_scan_files(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()

    for relative in SCAN_ROOTS:
        base = repo_root / relative
        if not base.exists():
            continue
        if base.is_file():
            if base not in seen and _should_scan(base):
                seen.add(base)
                paths.append(base)
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path in seen or not _should_scan(path):
                continue
            seen.add(path)
            paths.append(path)

    for relative in ROOT_SCAN_FILES:
        path = repo_root / relative
        if path.exists() and path.is_file() and path not in seen and _should_scan(path):
            seen.add(path)
            paths.append(path)

    return sorted(paths)


def collect_host_safety_contract_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []

    for relative_path, tokens in HOST_SAFETY_DOC_TOKENS_BY_FILE.items():
        text = _read_text(repo_root / relative_path)
        if text is None:
            errors.append(f"missing host-safety doc surface: {relative_path}")
            continue
        lowered = text.casefold()
        for token in tokens:
            if token.casefold() not in lowered:
                errors.append(f"{relative_path} is missing host-safety token: {token}")

    precommit_text = _read_text(repo_root / ".pre-commit-config.yaml")
    if precommit_text is None:
        errors.append("missing .pre-commit-config.yaml for host-safety gate")
    elif HOST_SAFETY_CHECK_TOKEN not in precommit_text:
        errors.append(".pre-commit-config.yaml is missing the host-safety gate token")

    workflow_text = _read_text(repo_root / ".github" / "workflows" / "ci.yml")
    if workflow_text is None:
        errors.append("missing .github/workflows/ci.yml for host-safety gate")
    elif HOST_SAFETY_CHECK_TOKEN not in workflow_text:
        errors.append(".github/workflows/ci.yml is missing the host-safety gate token")

    for path in _iter_scan_files(repo_root):
        relative_path = path.relative_to(repo_root).as_posix()
        if relative_path in SELF_AUDIT_IGNORED_PATHS:
            continue
        text = _read_text(path)
        if text is None:
            continue
        if path.suffix == ".py":
            errors.extend(_scan_python_file(path, relative_path, text))
        else:
            errors.extend(_scan_text_file(relative_path, text))

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors = collect_host_safety_contract_errors(repo_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("host safety contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
