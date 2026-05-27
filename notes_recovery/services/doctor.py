from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from importlib import resources
from typing import Any

from notes_recovery import config
from notes_recovery.io import ensure_safe_output_dir


def _check(name: str, status: str, summary: str, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": status,
        "summary": summary,
        "detail": detail,
    }


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def _command_available(command: str) -> bool:
    return shutil.which(command) is not None


def _notes_running() -> bool:
    if platform.system() != "Darwin":
        return False
    try:
        completed = subprocess.run(
            ["/usr/bin/pgrep", "-x", "Notes"],
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.returncode == 0
    except Exception:
        return False


def _demo_artifacts_available() -> bool:
    try:
        demo_dir = resources.files("notes_recovery").joinpath("resources", "demo")
    except Exception:
        return False
    required = (
        "sanitized-case-tree.txt",
        "sanitized-verification-summary.txt",
        "sanitized-operator-brief.md",
    )
    return all(demo_dir.joinpath(name).is_file() for name in required)


def _optional_extra_status() -> dict[str, dict[str, Any]]:
    ai_modules = ("httpx",)
    mcp_modules = ("mcp",)
    dashboard_modules = ("streamlit", "pandas", "networkx", "plotly")
    carve_modules = ("lz4", "liblzfse")

    ai_missing = [name for name in ai_modules if not _module_available(name)]
    mcp_missing = [name for name in mcp_modules if not _module_available(name)]
    dashboard_missing = [name for name in dashboard_modules if not _module_available(name)]
    carve_missing = [name for name in carve_modules if not _module_available(name)]

    return {
        "ai": {
            "installed": not ai_missing,
            "missing": ai_missing,
        },
        "mcp": {
            "installed": not mcp_missing,
            "missing": mcp_missing,
        },
        "dashboard": {
            "installed": not dashboard_missing,
            "missing": dashboard_missing,
        },
        "carve": {
            "installed": not carve_missing,
            "missing": carve_missing,
        },
    }


def _integration_status() -> dict[str, bool]:
    return {
        "docker": _command_available("docker"),
        "sqlite_dissect": _command_available("sqlite_dissect"),
        "strings": _command_available("strings"),
        "binwalk": _command_available("binwalk"),
    }


def run_doctor() -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    host_is_macos = platform.system() == "Darwin"
    if host_is_macos:
        checks.append(
            _check(
                "host-boundary",
                "pass",
                "Supported host boundary detected",
                "This host is macOS, which matches the supported workflow boundary.",
            )
        )
    else:
        checks.append(
            _check(
                "host-boundary",
                "warn",
                "Host is outside the supported recovery boundary",
                "You can still run the public demo, but the default Apple Notes workflow is documented for macOS only.",
            )
        )

    python_ok = sys.version_info >= (3, 11)
    if python_ok:
        checks.append(
            _check(
                "python",
                "pass",
                "Python runtime is supported",
                f"Detected Python {sys.version_info.major}.{sys.version_info.minor}; the project requires >= 3.11.",
            )
        )
    else:
        checks.append(
            _check(
                "python",
                "fail",
                "Python runtime is too old",
                f"Detected Python {sys.version_info.major}.{sys.version_info.minor}; install Python 3.11 or newer before continuing.",
            )
        )

    if _demo_artifacts_available():
        checks.append(
            _check(
                "demo-surface",
                "pass",
                "Public demo artifacts are available",
                "You can run `notes-recovery demo` for a zero-risk first look.",
            )
        )
    else:
        checks.append(
            _check(
                "demo-surface",
                "fail",
                "Public demo artifacts are missing",
                "The tracked demo bundle is incomplete, so the safest first-look path is currently broken.",
            )
        )

    default_paths = config.DEFAULT_PATHS
    notes_container = default_paths.notes_group_container.expanduser()
    spotlight_dir = default_paths.core_spotlight.expanduser()
    cache_dir = default_paths.notes_cache.expanduser()

    if notes_container.exists():
        checks.append(
            _check(
                "notes-default-path",
                "pass",
                "Default Apple Notes source path is present",
                f"Found Notes group container at {notes_container}.",
            )
        )
    else:
        checks.append(
            _check(
                "notes-default-path",
                "warn",
                "Default Apple Notes source path was not found",
                "The standard `snapshot/auto` path may not work on this host; stay on `demo` or point commands at an existing copied case manually.",
            )
        )

    if _notes_running():
        checks.append(
            _check(
                "notes-process",
                "warn",
                "Notes appears to be running",
                "Quit Notes before copying evidence so the source does not change underneath the workflow.",
            )
        )
    else:
        checks.append(
            _check(
                "notes-process",
                "pass",
                "Notes is not running",
                "The host does not appear to have a live Notes process changing the default source path right now.",
            )
        )

    try:
        ensure_safe_output_dir(
            config.DEFAULT_OUTPUT_ROOT,
            [notes_container, spotlight_dir, cache_dir],
            "Doctor",
        )
        checks.append(
            _check(
                "output-root",
                "pass",
                "Default output root is boundary-safe",
                f"`{config.DEFAULT_OUTPUT_ROOT}` does not collide with the default source directories.",
            )
        )
    except Exception as exc:
        checks.append(
            _check(
                "output-root",
                "fail",
                "Default output root is unsafe",
                str(exc),
            )
        )

    extras = _optional_extra_status()
    for extra_name, payload in extras.items():
        if payload["installed"]:
            checks.append(
                _check(
                    f"extra-{extra_name}",
                    "pass",
                    f"Optional `{extra_name}` surface is installed",
                    f"The `{extra_name}` dependency set is available on this machine.",
                )
            )
        else:
            missing_list = ", ".join(payload["missing"])
            checks.append(
                _check(
                    f"extra-{extra_name}",
                    "warn",
                    f"Optional `{extra_name}` surface is not installed",
                    f"Missing import(s): {missing_list}. Install `.[{extra_name}]` only if you need that optional surface.",
                )
            )

    integrations = _integration_status()
    available_integrations = [name for name, available in integrations.items() if available]
    missing_integrations = [name for name, available in integrations.items() if not available]
    checks.append(
        _check(
            "optional-integrations",
            "pass" if available_integrations else "warn",
            "Optional external-tool integrations were inspected",
            "Available: "
            + (", ".join(available_integrations) if available_integrations else "(none)")
            + " | Missing: "
            + (", ".join(missing_integrations) if missing_integrations else "(none)"),
        )
    )

    has_fail = any(item["status"] == "fail" for item in checks)
    ready_for_default_workflow = host_is_macos and python_ok and notes_container.exists()

    if has_fail:
        overall_status = "fix-first"
        recommended_next_step = "Fix the failing checks, then rerun `notes-recovery doctor`."
    elif ready_for_default_workflow:
        overall_status = "ready"
        recommended_next_step = (
            "Run `notes-recovery demo` if you want a zero-risk first look, or continue to the standard copied-evidence workflow with `notes-recovery auto ...`."
        )
    else:
        overall_status = "demo-only"
        recommended_next_step = (
            "Stay on `notes-recovery demo` for now, or use commands against an existing copied case root until the host boundary is fully satisfied."
        )

    return {
        "overall_status": overall_status,
        "supported_boundary": {
            "host_os": "macOS only",
            "workflow_style": "copy-first local recovery and review",
            "live_store_rule": "do not operate on the original live Notes store",
        },
        "checks": checks,
        "optional_extras": extras,
        "optional_integrations": integrations,
        "recommended_next_step": recommended_next_step,
    }


def render_doctor_report(payload: dict[str, Any]) -> str:
    lines = [
        "Noteyard doctor",
        "",
        f"Overall status: {payload['overall_status']}",
        "",
        "Boundary",
        f"- Host OS support: {payload['supported_boundary']['host_os']}",
        f"- Workflow style: {payload['supported_boundary']['workflow_style']}",
        f"- Core rule: {payload['supported_boundary']['live_store_rule']}",
        "",
        "Checks",
    ]
    for item in payload["checks"]:
        lines.append(
            f"- [{item['status'].upper()}] {item['summary']} — {item['detail']}"
        )
    lines.extend(
        [
            "",
            "Recommended next step",
            f"- {payload['recommended_next_step']}",
        ]
    )
    return "\n".join(lines) + "\n"
