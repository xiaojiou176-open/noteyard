from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from notes_recovery.case_contract import CASE_DIR_PLUGINS_OUTPUT
from notes_recovery.config import DEFAULT_PLUGINS_CONFIG
from notes_recovery.io import ensure_dir
from notes_recovery.logging import eprint
from notes_recovery.models import PluginTool

PLUGIN_CONTRACT_VERSION = "2026-04-01.v1"

FORBIDDEN_PLUGIN_EXECUTABLES = {
    "kill",
    "killall",
    "pkill",
    "launchctl",
    "osascript",
    "sudo",
}

FORBIDDEN_PLUGIN_SHELL_EXECUTABLES = {
    "bash",
    "fish",
    "ksh",
    "sh",
    "zsh",
}

FORBIDDEN_PLUGIN_INLINE_EVAL_FLAGS = {
    "lua": {"-e"},
    "node": {"-e", "-p"},
    "perl": {"-e"},
    "php": {"-r"},
    "python": {"-c"},
    "python3": {"-c"},
    "ruby": {"-e"},
}

FORBIDDEN_PLUGIN_COMMAND_PATTERNS = (
    ("kill -9", re.compile(r"(?<![A-Za-z0-9_])kill\s+-9\b")),
    ("rm -rf", re.compile(r"(?<![A-Za-z0-9_])rm\s+-rf\b")),
    ("os.kill(...)", re.compile(r"\bos\.kill\s*\(")),
    ("process.kill(...)", re.compile(r"\bprocess\.kill\s*\(")),
    ("System Events", re.compile(r"System Events", re.IGNORECASE)),
    ("AppleEvent", re.compile(r"\bAppleEvent\b", re.IGNORECASE)),
    ("loginwindow", re.compile(r"\bloginwindow\b", re.IGNORECASE)),
    ("showForceQuitPanel", re.compile(r"\bshowForceQuitPanel\b", re.IGNORECASE)),
)


def _iter_candidate_executable_indexes(command: list[str]) -> list[int]:
    if not command:
        return []

    indexes = [0]
    current_index = 0

    while current_index < len(command):
        executable = Path(command[current_index]).name.casefold()
        next_index: Optional[int] = None

        if executable == "env":
            probe_index = current_index + 1
            while probe_index < len(command):
                part = command[probe_index]
                if part == "--":
                    probe_index += 1
                    break
                if part.startswith("-"):
                    probe_index += 1
                    continue
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", part):
                    probe_index += 1
                    continue
                break
            if probe_index < len(command):
                next_index = probe_index
        elif executable == "command":
            probe_index = current_index + 1
            while probe_index < len(command) and command[probe_index].startswith("-"):
                probe_index += 1
            if probe_index < len(command):
                next_index = probe_index

        if next_index is None or next_index in indexes:
            break

        indexes.append(next_index)
        current_index = next_index

    return indexes


def _read_plugins_config_data(path: Path) -> dict[str, object]:
    ensure_plugins_config(path)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        raise RuntimeError(f"Failed to read plugin config: {path} -> {exc}")
    if not isinstance(data, dict):
        raise RuntimeError(f"Plugin config must be a JSON object: {path}")
    return data


def _normalize_command(command_raw: object) -> tuple[list[str], Optional[str]]:
    if isinstance(command_raw, str):
        try:
            return shlex.split(command_raw), None
        except ValueError as exc:
            return [], f"Tool command string could not be parsed: {exc}"
    if command_raw in (None, ""):
        return [], None
    if not isinstance(command_raw, list):
        return [], "Tool command must be a string or list of strings."

    command: list[str] = []
    for index, part in enumerate(command_raw, start=1):
        text = str(part).strip()
        if not text:
            return [], f"Tool command item #{index} must be a non-empty string."
        command.append(text)
    return command, None


def _normalize_timeout(timeout_raw: object) -> tuple[Optional[int], Optional[str]]:
    if timeout_raw in (None, ""):
        return None, None

    try:
        numeric = float(timeout_raw)
    except (TypeError, ValueError):
        return None, "timeout_sec must be a positive integer when provided."

    if not numeric.is_integer() or int(numeric) <= 0:
        return None, "timeout_sec must be a positive integer when provided."

    return int(numeric), None


def _normalize_tool_item(item: object, index: int) -> tuple[PluginTool, list[str]]:
    issues: list[str] = []
    if not isinstance(item, dict):
        issues.append(f"Tool entry #{index} must be a JSON object.")
        return PluginTool(
            name="",
            command=[],
            enabled=False,
            output_dir=f"{CASE_DIR_PLUGINS_OUTPUT}/tool_{index}",
            timeout_sec=None,
        ), issues

    name = str(item.get("name", "")).strip()
    command, command_issue = _normalize_command(item.get("command", []))
    if command_issue:
        issues.append(command_issue)

    enabled = bool(item.get("enabled", False))
    output_dir = str(item.get("output_dir", f"{CASE_DIR_PLUGINS_OUTPUT}/{name}")).strip()

    timeout_sec, timeout_issue = _normalize_timeout(item.get("timeout_sec", None))
    if timeout_issue:
        issues.append(timeout_issue)

    return PluginTool(
        name=name,
        command=command,
        enabled=enabled,
        output_dir=output_dir,
        timeout_sec=timeout_sec,
    ), issues


def _build_plugin_command_mapping(root_dir: Path, db_path: Path, out_dir: Path) -> dict[str, str]:
    return {
        "db": str(db_path),
        "db_path": str(db_path),
        "db_dir": str(db_path.parent),
        "root": str(root_dir),
        "out": str(out_dir),
    }


def ensure_plugins_config(path: Path) -> None:
    if path.exists():
        return
    ensure_dir(path.parent)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(DEFAULT_PLUGINS_CONFIG, f, ensure_ascii=True, indent=2)
    except Exception as exc:
        raise RuntimeError(f"Failed to write plugin config: {path} -> {exc}")


def _validate_command_host_safety(command: list[str]) -> Optional[str]:
    if not command:
        return None

    for executable_index in _iter_candidate_executable_indexes(command):
        raw_executable = command[executable_index]
        executable = Path(raw_executable).name.casefold()

        if executable in FORBIDDEN_PLUGIN_EXECUTABLES:
            return f"Tool command must not invoke host-control executable `{raw_executable}`."

        if executable in FORBIDDEN_PLUGIN_SHELL_EXECUTABLES:
            return f"Tool command must not launch through shell trampoline executable `{raw_executable}`."

        inline_flags = FORBIDDEN_PLUGIN_INLINE_EVAL_FLAGS.get(executable)
        if inline_flags and any(part in inline_flags for part in command[executable_index + 1 :]):
            return (
                f"Tool command must not use inline interpreter evaluation via `{raw_executable}`."
            )

    rendered = " ".join(command)
    for label, pattern in FORBIDDEN_PLUGIN_COMMAND_PATTERNS:
        if pattern.search(rendered):
            return f"Tool command contains forbidden host-control token `{label}`."

    return None


def load_plugins_config(path: Path) -> list[PluginTool]:
    data = _read_plugins_config_data(path)

    raw_tools = data.get("tools", [])
    if not isinstance(raw_tools, list):
        raise RuntimeError(f"Plugin config `tools` must be a list: {path}")

    tools = []
    for index, item in enumerate(raw_tools, start=1):
        tool, _ = _normalize_tool_item(item, index)
        tools.append(tool)
    return tools


def _validate_tool_payload(
    tool: PluginTool,
    *,
    normalization_issues: Optional[list[str]] = None,
    root_dir: Optional[Path],
    db_path: Optional[Path],
) -> dict[str, object]:
    checks: list[dict[str, str]] = []
    errors: list[str] = list(normalization_issues or [])
    warnings: list[str] = []

    if not tool.name:
        errors.append("Tool is missing a non-empty `name`.")

    if not tool.command:
        errors.append("Tool command is empty.")
    elif is_placeholder_command(tool.command):
        warnings.append("Tool command still looks like a placeholder and will be skipped by the runner.")

    rendered_command = list(tool.command)
    if root_dir is not None and db_path is not None and tool.command:
        rendered_command = format_command(
            tool.command,
            _build_plugin_command_mapping(root_dir, db_path, root_dir / tool.output_dir),
        )

    host_safety_issue = _validate_command_host_safety(rendered_command)
    if host_safety_issue:
        errors.append(host_safety_issue)

    if tool.output_dir:
        try:
            if root_dir is None:
                resolve_plugin_output_dir(Path("."), tool.output_dir, tool.name or "<unnamed>")
            else:
                resolve_plugin_output_dir(root_dir, tool.output_dir, tool.name or "<unnamed>")
            checks.append(
                {
                    "name": "output_dir",
                    "status": "ok",
                    "detail": "Output directory stays relative to the case root.",
                }
            )
        except Exception as exc:
            errors.append(str(exc))
    else:
        errors.append("Tool output_dir is empty.")

    if tool.enabled:
        checks.append(
            {
                "name": "enabled",
                "status": "ok",
                "detail": "Tool is enabled and can run during a real plugin pass.",
            }
        )
    else:
        checks.append(
            {
                "name": "enabled",
                "status": "ok",
                "detail": "Tool is disabled by config and stays outside the default baseline path.",
            }
        )

    executable_hint = rendered_command[0] if rendered_command else ""
    executable_available = False
    if executable_hint:
        executable_available = shutil.which(executable_hint) is not None
        if not tool.enabled:
            checks.append(
                {
                    "name": "host_dependency",
                    "status": "ok",
                    "detail": "Host dependency check is informational only while the tool stays disabled.",
                }
            )
        elif executable_available:
            checks.append(
                {
                    "name": "command",
                    "status": "ok",
                    "detail": f"Executable `{executable_hint}` is available on this host.",
                }
            )
        else:
            warnings.append(
                f"Executable `{executable_hint}` is not currently available on this host."
            )

    if tool.timeout_sec is not None and tool.timeout_sec <= 0:
        errors.append("timeout_sec must be a positive integer when provided.")
    elif tool.timeout_sec is not None:
        checks.append(
            {
                "name": "timeout_sec",
                "status": "ok",
                "detail": f"timeout_sec is set to {tool.timeout_sec} seconds.",
            }
        )

    if errors:
        status = "fail"
    elif warnings:
        status = "warn"
    else:
        status = "ok"

    return {
        "name": tool.name or "<unnamed>",
        "enabled": tool.enabled,
        "status": status,
        "issues": errors + warnings,
        "reasons": errors + warnings,
        "checks": checks,
        "command": rendered_command,
        "output_dir": tool.output_dir,
        "timeout_sec": tool.timeout_sec,
        "placeholder": bool(tool.command and is_placeholder_command(tool.command)),
        "executable_available": executable_available if executable_hint else False,
    }


def validate_plugins_config(
    config_path: Path,
    *,
    root_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> dict[str, object]:
    try:
        data = _read_plugins_config_data(config_path)
    except RuntimeError as exc:
        return {
            "kind": "plugin_contract_v1",
            "contract_version": PLUGIN_CONTRACT_VERSION,
            "status": "fail",
            "overall_status": "fail",
            "config_path": str(config_path),
            "root_dir": str(root_dir) if root_dir is not None else "",
            "db_path": str(db_path) if db_path is not None else "",
            "tool_count": 0,
            "summary": {"ok": 0, "warn": 0, "fail": 1},
            "tools": [],
            "issues": [str(exc)],
            "recommended_next_step": "Fix the plugin config file shape before trusting it in a real case run.",
        }

    raw_tools = data.get("tools", [])
    if not isinstance(raw_tools, list):
        return {
            "kind": "plugin_contract_v1",
            "contract_version": PLUGIN_CONTRACT_VERSION,
            "status": "fail",
            "overall_status": "fail",
            "config_path": str(config_path),
            "root_dir": str(root_dir) if root_dir is not None else "",
            "db_path": str(db_path) if db_path is not None else "",
            "tool_count": 0,
            "summary": {"ok": 0, "warn": 0, "fail": 1},
            "tools": [],
            "issues": ["Plugin config `tools` must be a list."],
            "recommended_next_step": "Fix the plugin config file shape before trusting it in a real case run.",
        }

    validations = [
        _validate_tool_payload(
            tool,
            normalization_issues=issues,
            root_dir=root_dir,
            db_path=db_path,
        )
        for index, item in enumerate(raw_tools, start=1)
        for tool, issues in [_normalize_tool_item(item, index)]
    ]

    fail_count = sum(1 for item in validations if item["status"] == "fail")
    warn_count = sum(1 for item in validations if item["status"] == "warn")
    ok_count = sum(1 for item in validations if item["status"] == "ok")

    if fail_count:
        overall_status = "fail"
        recommended_next_step = "Fix the plugin contract errors before trusting this plugin config in a real case run."
    elif warn_count:
        overall_status = "warn"
        recommended_next_step = "Review the warnings, then enable only the tools whose commands and dependencies are actually available on this host."
    else:
        overall_status = "ok"
        recommended_next_step = "The plugin contract looks internally consistent. Enable only the tools you intentionally want to run for this case."

    return {
        "kind": "plugin_contract_v1",
        "contract_version": PLUGIN_CONTRACT_VERSION,
        "status": overall_status,
        "config_path": str(config_path),
        "root_dir": str(root_dir) if root_dir is not None else "",
        "db_path": str(db_path) if db_path is not None else "",
        "tool_count": len(validations),
        "overall_status": overall_status,
        "summary": {
            "ok": ok_count,
            "warn": warn_count,
            "fail": fail_count,
        },
        "tools": validations,
        "issues": [],
        "recommended_next_step": recommended_next_step,
    }


def render_plugins_validation_report(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    lines = [
        "Plugin contract validation",
        "",
        f"Contract kind: {payload.get('kind', 'plugin_contract_v1')}",
        f"Contract version: {payload['contract_version']}",
        f"Overall status: {payload.get('status', payload['overall_status'])}",
        f"Config path: {payload['config_path']}",
    ]
    if payload.get("root_dir"):
        lines.append(f"Case root: {payload['root_dir']}")
    if payload.get("db_path"):
        lines.append(f"Database path: {payload['db_path']}")
    lines.extend(
        [
            "",
            "Summary",
            f"- OK: {summary['ok']}",
            f"- WARN: {summary['warn']}",
            f"- FAIL: {summary['fail']}",
            "",
            "Tools",
        ]
    )
    for item in payload["tools"]:
        lines.append(
            f"- [{str(item['status']).upper()}] {item['name']} (enabled={item['enabled']}, output_dir={item['output_dir']})"
        )
        issues = item.get("reasons", item.get("issues", []))
        if issues:
            for issue in issues:
                lines.append(f"  - {issue}")
        else:
            lines.append("  - No contract issues detected.")
    lines.extend(["", "Recommended next step", f"- {payload['recommended_next_step']}"])
    return "\n".join(lines) + "\n"


def is_placeholder_command(command: list[str]) -> bool:
    if not command:
        return True
    joined = " ".join(command).lower()
    return "path/to" in joined or "<" in joined or "replace" in joined


def format_command(command: list[str], mapping: dict[str, str]) -> list[str]:
    rendered = []
    for part in command:
        try:
            rendered.append(part.format(**mapping))
        except Exception:
            rendered.append(part)
    return rendered


def resolve_plugin_output_dir(root_dir: Path, output_dir: str, tool_name: str) -> Optional[Path]:
    candidate = Path(output_dir)
    if candidate.is_absolute():
        raise RuntimeError(f"Plugin {tool_name} output_dir must be a relative path: {output_dir}")
    if ".." in candidate.parts:
        raise RuntimeError(f"Plugin {tool_name} output_dir must not contain '..': {output_dir}")
    return root_dir / candidate


def run_plugins(
    root_dir: Path,
    db_path: Path,
    config_path: Path,
    enable_all: bool,
    run_ts: Optional[str] = None,
) -> None:
    if not db_path.exists():
        raise RuntimeError(f"Database does not exist: {db_path}")
    tools = load_plugins_config(config_path)
    if not tools:
        print("No runnable external-tool configuration was found.")
        return
    manifest_path = root_dir / ("plugins_manifest.jsonl" if not run_ts else f"plugins_manifest_{run_ts}.jsonl")

    for tool in tools:
        if not tool.name:
            continue
        if not tool.enabled and not enable_all:
            try:
                with manifest_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "tool": tool.name,
                        "status": "skipped",
                        "reason": "disabled",
                        "output_dir": tool.output_dir,
                        "timeout_sec": tool.timeout_sec,
                    }, ensure_ascii=True) + "\n")
            except Exception:
                pass
            continue
        if is_placeholder_command(tool.command):
            eprint(f"Plugin {tool.name} does not have a complete command yet. Skipping.")
            try:
                with manifest_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "tool": tool.name,
                        "status": "skipped",
                        "reason": "placeholder",
                        "output_dir": tool.output_dir,
                        "timeout_sec": tool.timeout_sec,
                    }, ensure_ascii=True) + "\n")
            except Exception:
                pass
            continue

        try:
            out_dir = resolve_plugin_output_dir(root_dir, tool.output_dir, tool.name)
        except Exception as exc:
            eprint(str(exc))
            try:
                with manifest_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "tool": tool.name,
                        "status": "skipped",
                        "reason": str(exc),
                        "output_dir": tool.output_dir,
                        "timeout_sec": tool.timeout_sec,
                    }, ensure_ascii=True) + "\n")
            except Exception:
                pass
            continue
        if run_ts:
            out_dir = out_dir.with_name(f"{out_dir.name}_{run_ts}")
        ensure_dir(out_dir)
        mapping = {
            **_build_plugin_command_mapping(root_dir, db_path, out_dir),
        }
        cmd = format_command(tool.command, mapping)
        host_safety_issue = _validate_command_host_safety(cmd)
        if host_safety_issue:
            eprint(f"Plugin {tool.name} violates the host-safety contract. Skipping.")
            try:
                with manifest_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "tool": tool.name,
                        "status": "skipped",
                        "reason": host_safety_issue,
                        "output_dir": tool.output_dir,
                        "timeout_sec": tool.timeout_sec,
                        "command": cmd,
                    }, ensure_ascii=True) + "\n")
            except Exception as exc:
                eprint(f"Failed to write plugin manifest entry for {tool.name}: {exc}")
            continue
        log_path = out_dir / "plugin.log"
        try:
            start_time = time.time()
            with log_path.open("w", encoding="utf-8") as log_file:
                subprocess.run(
                    cmd,
                    check=True,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=tool.timeout_sec,
                )
            print(f"External tool completed: {tool.name} -> {out_dir}")
            try:
                with manifest_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "tool": tool.name,
                        "status": "ok",
                        "output_dir": str(out_dir),
                        "timeout_sec": tool.timeout_sec,
                        "elapsed_ms": int((time.time() - start_time) * 1000),
                        "command": cmd,
                    }, ensure_ascii=True) + "\n")
            except Exception:
                pass
        except subprocess.CalledProcessError as exc:
            try:
                with log_path.open("a", encoding="utf-8") as f:
                    f.write("\n[error]\n")
                    f.write(str(exc))
            except Exception:
                pass
            eprint(f"External tool failed: {tool.name} (see {log_path})")
            try:
                with manifest_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "tool": tool.name,
                        "status": "failed",
                        "output_dir": str(out_dir),
                        "timeout_sec": tool.timeout_sec,
                        "elapsed_ms": int((time.time() - start_time) * 1000),
                        "command": cmd,
                        "error": str(exc),
                    }, ensure_ascii=True) + "\n")
            except Exception:
                pass
        except subprocess.TimeoutExpired:
            try:
                with log_path.open("a", encoding="utf-8") as f:
                    f.write("\n[timeout]\n")
            except Exception:
                pass
            eprint(f"External tool timed out: {tool.name} (see {log_path})")
            try:
                with manifest_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "tool": tool.name,
                        "status": "timeout",
                        "output_dir": str(out_dir),
                        "timeout_sec": tool.timeout_sec,
                        "command": cmd,
                    }, ensure_ascii=True) + "\n")
            except Exception:
                pass
