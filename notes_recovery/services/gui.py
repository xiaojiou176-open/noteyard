from __future__ import annotations

import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from notes_recovery.config import (
    DEFAULT_OUTPUT_ROOT,
    PROTOBUF_MAX_NOTES_DEFAULT,
    PROTOBUF_MAX_ZDATA_MB_DEFAULT,
    SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT,
    SPOTLIGHT_PARSE_MAX_FILES_DEFAULT,
    SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT,
    SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT,
    SPOTLIGHT_PARSE_MIN_STRING_LEN,
)
from notes_recovery.core.pipeline import build_timestamped_dir, timestamp_now
from notes_recovery.io import (
    require_float_range,
    require_non_negative_float,
    require_non_negative_int,
    require_positive_int,
    resolve_path,
)
from notes_recovery.logging import DEFAULT_LOG_LEVEL, LOG_CONTEXT, configure_logging, resolve_log_path
from notes_recovery.services.auto import auto_run


class QueueWriter:
    def __init__(self, q: queue.Queue) -> None:
        self.q = q

    def write(self, text: str) -> None:
        if text:
            self.q.put(text)

    def flush(self) -> None:
        return None


def open_in_file_manager(path: Path) -> None:
    try:
        if not path.exists():
            raise RuntimeError(f"Path does not exist: {path}")
        subprocess.run(["/usr/bin/open", str(path)], check=False)
    except Exception as exc:
        raise RuntimeError(f"Failed to open directory: {path} -> {exc}")


def validate_int_text(value: str) -> bool:
    if value == "":
        return True
    return value.isdigit()


def validate_float_text(value: str) -> bool:
    if value == "":
        return True
    try:
        float(value)
        return True
    except ValueError:
        return False


# =============================================================================
# GUI Mode
# =============================================================================

def run_gui() -> None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except Exception as exc:
        raise RuntimeError(f"Tkinter is unavailable: {exc}")

    root = tk.Tk()
    root.title("Apple Notes Recovery - Guided UI")
    root.geometry("760x720")
    root.minsize(700, 640)

    style = ttk.Style(root)
    try:
        if "aqua" in style.theme_names():
            style.theme_use("aqua")
    except Exception:
        pass

    q: queue.Queue = queue.Queue()
    status_var = tk.StringVar(value="Ready")
    summary_var = tk.StringVar(value="Selected steps: not started")
    last_out_dir: list[Optional[Path]] = [None]
    validate_int_cmd = (root.register(validate_int_text), "%P")
    validate_float_cmd = (root.register(validate_float_text), "%P")

    def append_log(text: str) -> None:
        log_box.configure(state="normal")
        log_box.insert("end", text)
        log_box.see("end")
        log_box.configure(state="disabled")

    def capture_output_dir(text: str) -> None:
        for line in text.splitlines():
            if "Timestamped output directory:" in line:
                parts = line.split(":", 1)
                if len(parts) < 2:
                    continue
                path_str = parts[1].strip()
                if path_str:
                    try:
                        last_out_dir[0] = resolve_path(path_str)
                    except Exception:
                        continue

    def log_pump() -> None:
        while True:
            try:
                msg = q.get_nowait()
            except queue.Empty:
                break
            if msg == "__DONE__":
                start_btn.config(state="normal")
                progress.stop()
                status_var.set("Completed")
            else:
                capture_output_dir(msg)
                append_log(msg)
        root.after(100, log_pump)

    def browse_dir() -> None:
        path = filedialog.askdirectory()
        if path:
            out_var.set(path)

    def open_output_dir() -> None:
        target = last_out_dir[0] or resolve_path(out_var.get())
        try:
            open_in_file_manager(target)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def copy_log() -> None:
        try:
            content = log_box.get("1.0", "end").strip()
            root.clipboard_clear()
            root.clipboard_append(content)
            status_var.set("Log copied")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to copy the log: {exc}")

    def reset_form() -> None:
        out_var.set(str(DEFAULT_OUTPUT_ROOT))
        keyword_var.set("")
        apply_preset("recommended")
        status_var.set("Reset to the recommended preset")

    def validate_inputs() -> Optional[str]:
        try:
            if report_var.get():
                require_positive_int(report_max_items_var.get(), "maximum report items")
            require_positive_int(carve_max_hits_var.get(), "maximum carve hits")
            require_float_range(carve_min_ratio_var.get(), "minimum carve readability ratio", 0.0, 1.0)
            if run_protobuf_var.get():
                require_positive_int(protobuf_max_notes_var.get(), "maximum protobuf note count")
                require_positive_int(protobuf_max_zdata_mb_var.get(), "maximum protobuf ZDATA size (MB)")
            if run_spotlight_parse_var.get():
                require_positive_int(spotlight_parse_max_files_var.get(), "maximum Spotlight file count")
                require_positive_int(spotlight_parse_max_bytes_var.get(), "maximum Spotlight file size (bytes)")
                require_positive_int(spotlight_parse_min_len_var.get(), "minimum Spotlight string length")
                require_positive_int(spotlight_parse_max_chars_var.get(), "maximum Spotlight characters per file")
                require_positive_int(spotlight_parse_max_rows_var.get(), "maximum Spotlight SQLite rows")
            if verify_var.get():
                require_positive_int(verify_top_var.get(), "verification Top count")
                require_positive_int(verify_preview_var.get(), "preview length")
                if verify_deep_var.get():
                    require_non_negative_int(verify_deep_max_mb_var.get(), "maximum deep-scan file size (MB)")
                    require_positive_int(verify_deep_max_hits_var.get(), "maximum deep-scan hits per file")
                if verify_fuzzy_var.get():
                    require_float_range(verify_fuzzy_threshold_var.get(), "fuzzy-match threshold", 0.0, 1.0)
                    require_non_negative_float(verify_fuzzy_boost_var.get(), "fuzzy-match boost factor")
                    require_positive_int(verify_fuzzy_max_len_var.get(), "maximum fuzzy-match comparison length")
            if run_recover_var.get():
                if not recover_lost_and_found_var.get().strip():
                    return "The lost_and_found table name cannot be empty."
            if log_to_file_var.get():
                require_non_negative_int(log_max_bytes_var.get(), "log size limit (bytes)")
                require_non_negative_int(log_backup_count_var.get(), "log backup count")
                if log_backup_count_var.get() > 0 and log_max_bytes_var.get() <= 0:
                    return "A log size limit (bytes) is required when log backup count is set."
                if not log_time_format_var.get().strip():
                    return "Log timestamp format cannot be empty."
        except Exception as exc:
            return str(exc)
        return None

    def estimate_speed_label() -> str:
        score = 0
        if include_spotlight_var.get():
            score += 1
        if include_cache_var.get():
            score += 1
        if run_wal_var.get():
            score += 1
        if run_query_var.get():
            score += 1
        if run_carve_var.get():
            score += 2
        if run_recover_var.get():
            score += 2
        if run_protobuf_var.get():
            score += 1
        if run_spotlight_parse_var.get():
            score += 2
        if run_plugins_var.get():
            score += 1
        if verify_var.get():
            score += 1
        if verify_var.get() and verify_deep_var.get():
            score += 2
        if score <= 3:
            return "Estimated runtime: fast"
        if score <= 6:
            return "Estimated runtime: medium"
        return "Estimated runtime: slow"

    def worker() -> None:
        writer = QueueWriter(q)
        old_out, old_err = sys.stdout, sys.stderr
        log_path = None
        try:
            log_run_ts = timestamp_now()
            base_out = resolve_path(out_var.get())
            expected_root = build_timestamped_dir(base_out, log_run_ts)
            last_out_dir[0] = expected_root
            if log_to_file_var.get():
                log_path = resolve_log_path(
                    log_file_var.get(),
                    None,
                    log_run_ts,
                    expected_root,
                    "gui",
                )
            configure_logging(
                log_level_var.get(),
                log_path,
                quiet=False,
                append=log_append_var.get(),
                max_bytes=log_max_bytes_var.get(),
                backup_count=log_backup_count_var.get(),
                stream_out=writer,
                stream_err=writer,
                time_format=log_time_format_var.get(),
                use_utc=log_utc_var.get(),
                console_level=log_console_level_var.get(),
                json_enabled=log_json_var.get(),
                command="gui",
                session=log_run_ts,
            )
            if log_path:
                print(f"Log file: {log_path}")
            plugins_config_value = plugins_config_var.get().strip()
            plugins_config_path = resolve_path(plugins_config_value) if plugins_config_value else None
            auto_run(
                base_out,
                keyword_var.get() or None,
                include_spotlight_var.get(),
                include_cache_var.get(),
                run_wal_var.get(),
                run_query_var.get(),
                run_carve_var.get(),
                run_recover_var.get(),
                recover_ignore_freelist_var.get(),
                recover_lost_and_found_var.get(),
                run_plugins_var.get(),
                plugins_config_path,
                plugins_enable_all_var.get(),
                report_var.get(),
                None,
                report_max_items_var.get(),
                carve_max_hits_var.get(),
                2 * 1024 * 1024,
                32,
                carve_min_ratio_var.get(),
                run_protobuf_var.get(),
                protobuf_max_notes_var.get(),
                protobuf_max_zdata_mb_var.get(),
                run_spotlight_parse_var.get(),
                spotlight_parse_max_files_var.get(),
                spotlight_parse_max_bytes_var.get(),
                spotlight_parse_min_len_var.get(),
                spotlight_parse_max_chars_var.get(),
                spotlight_parse_max_rows_var.get(),
                verify_var.get(),
                verify_top_var.get(),
                verify_preview_var.get(),
                None,
                verify_deep_var.get(),
                verify_deep_max_mb_var.get(),
                verify_deep_max_hits_var.get(),
                verify_deep_all_var.get(),
                verify_match_all_var.get(),
                verify_fuzzy_var.get(),
                verify_fuzzy_threshold_var.get(),
                verify_fuzzy_boost_var.get(),
                verify_fuzzy_max_len_var.get(),
                run_ts_override=log_run_ts,
            )
        except Exception as exc:
            q.put(f"Error: {exc}\n")
        finally:
            LOG_CONTEXT.close()
            sys.stdout, sys.stderr = old_out, old_err
            q.put("__DONE__")

    def start() -> None:
        if not out_var.get().strip():
            messagebox.showerror("Error", "An output directory is required.")
            return
        if verify_var.get() and not keyword_var.get().strip():
            messagebox.showerror("Error", "A keyword is required when one-shot verification is enabled.")
            return
        error = validate_inputs()
        if error:
            messagebox.showerror("Parameter error", error)
            return
        log_box.configure(state="normal")
        log_box.delete("1.0", "end")
        log_box.configure(state="disabled")
        last_out_dir[0] = None
        start_btn.config(state="disabled")
        status_var.set("Running")
        progress.start(10)
        append_log("Recovery run started. Keep Notes closed while this is running.\n")
        append_log(f"Output directory: {out_var.get().strip()}\n")
        if keyword_var.get().strip():
            append_log(f"Keyword: {keyword_var.get().strip()}\n")
        append_log(f"{summary_var.get()}\n\n")
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    out_var = tk.StringVar(value=str(DEFAULT_OUTPUT_ROOT))
    keyword_var = tk.StringVar(value="")
    include_spotlight_var = tk.BooleanVar(value=True)
    include_cache_var = tk.BooleanVar(value=True)
    run_wal_var = tk.BooleanVar(value=True)
    run_query_var = tk.BooleanVar(value=True)
    run_carve_var = tk.BooleanVar(value=True)
    run_recover_var = tk.BooleanVar(value=False)
    recover_ignore_freelist_var = tk.BooleanVar(value=False)
    recover_lost_and_found_var = tk.StringVar(value="lost_and_found")
    run_protobuf_var = tk.BooleanVar(value=False)
    protobuf_max_notes_var = tk.IntVar(value=PROTOBUF_MAX_NOTES_DEFAULT)
    protobuf_max_zdata_mb_var = tk.IntVar(value=PROTOBUF_MAX_ZDATA_MB_DEFAULT)
    run_spotlight_parse_var = tk.BooleanVar(value=False)
    spotlight_parse_max_files_var = tk.IntVar(value=SPOTLIGHT_PARSE_MAX_FILES_DEFAULT)
    spotlight_parse_max_bytes_var = tk.IntVar(value=SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT)
    spotlight_parse_min_len_var = tk.IntVar(value=SPOTLIGHT_PARSE_MIN_STRING_LEN)
    spotlight_parse_max_chars_var = tk.IntVar(value=SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT)
    spotlight_parse_max_rows_var = tk.IntVar(value=SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT)
    run_plugins_var = tk.BooleanVar(value=False)
    plugins_config_var = tk.StringVar(value="")
    plugins_enable_all_var = tk.BooleanVar(value=False)
    report_var = tk.BooleanVar(value=True)
    report_max_items_var = tk.IntVar(value=50)
    carve_max_hits_var = tk.IntVar(value=200)
    carve_min_ratio_var = tk.DoubleVar(value=0.55)
    verify_var = tk.BooleanVar(value=True)
    verify_top_var = tk.IntVar(value=10)
    verify_preview_var = tk.IntVar(value=300)
    verify_deep_var = tk.BooleanVar(value=True)
    verify_deep_all_var = tk.BooleanVar(value=True)
    verify_deep_max_mb_var = tk.IntVar(value=0)
    verify_deep_max_hits_var = tk.IntVar(value=200)
    verify_match_all_var = tk.BooleanVar(value=False)
    verify_fuzzy_var = tk.BooleanVar(value=True)
    verify_fuzzy_threshold_var = tk.DoubleVar(value=0.72)
    verify_fuzzy_boost_var = tk.DoubleVar(value=6.0)
    verify_fuzzy_max_len_var = tk.IntVar(value=2000)
    log_to_file_var = tk.BooleanVar(value=True)
    log_level_var = tk.StringVar(value=DEFAULT_LOG_LEVEL)
    log_file_var = tk.StringVar(value="auto")
    log_append_var = tk.BooleanVar(value=False)
    log_max_bytes_var = tk.IntVar(value=0)
    log_backup_count_var = tk.IntVar(value=0)
    log_time_format_var = tk.StringVar(value="%Y-%m-%d %H:%M:%S")
    log_utc_var = tk.BooleanVar(value=False)
    log_json_var = tk.BooleanVar(value=False)
    log_console_level_var = tk.StringVar(value=DEFAULT_LOG_LEVEL)

    paned = ttk.Panedwindow(root, orient="vertical")
    paned.pack(fill="both", expand=True)

    config_host = ttk.Frame(paned)
    log_host = ttk.Frame(paned)
    paned.add(config_host, weight=3)
    paned.add(log_host, weight=2)

    canvas = tk.Canvas(config_host, highlightthickness=0)
    vscroll = ttk.Scrollbar(config_host, orient="vertical", command=canvas.yview)
    content = ttk.Frame(canvas)

    def refresh_scroll(_event: Optional[tk.Event] = None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_mousewheel(event: tk.Event) -> None:
        delta = event.delta if event.delta else 0
        if delta == 0:
            return
        canvas.yview_scroll(int(-1 * (delta / 120)), "units")

    content.bind("<Configure>", refresh_scroll)
    canvas.create_window((0, 0), window=content, anchor="nw")
    canvas.configure(yscrollcommand=vscroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    vscroll.pack(side="right", fill="y")
    canvas.bind_all("<MouseWheel>", on_mousewheel)
    canvas.bind_all("<Button-4>", lambda _event: canvas.yview_scroll(-1, "units"))
    canvas.bind_all("<Button-5>", lambda _event: canvas.yview_scroll(1, "units"))

    intro = ttk.Labelframe(content, text="Usage notes")
    intro.grid(row=0, column=0, sticky="we", padx=12, pady=(12, 6))
    intro.columnconfigure(0, weight=1)
    ttk.Label(
        intro,
        text=(
            "Important: this tool only works on copied evidence. Close Notes first to avoid overwriting data.\n"
            "Workflow: 1) copy evidence  2) isolate WAL  3) query the database  4) carve data  5) generate a report"
        ),
        justify="left",
    ).grid(row=0, column=0, sticky="w", padx=8, pady=6)

    basic = ttk.Labelframe(content, text="Basic settings")
    basic.grid(row=1, column=0, sticky="we", padx=12, pady=6)
    basic.columnconfigure(1, weight=1)
    ttk.Label(basic, text="Output directory (stores all copies and results)").grid(row=0, column=0, sticky="w", padx=8, pady=4)
    out_entry = ttk.Entry(basic, textvariable=out_var)
    out_entry.grid(row=0, column=1, sticky="we", padx=6, pady=4)
    ttk.Button(basic, text="Browse...", command=browse_dir).grid(row=0, column=2, padx=6, pady=4)
    ttk.Label(basic, text="Keyword (optional, used for hit stats and highlighting; comma/pipe separators supported)").grid(
        row=1, column=0, sticky="w", padx=8, pady=4
    )
    keyword_entry = ttk.Entry(basic, textvariable=keyword_var)
    keyword_entry.grid(row=1, column=1, sticky="we", padx=6, pady=4)

    options = ttk.Labelframe(content, text="Step selection (keeping the defaults is recommended)")
    options.grid(row=2, column=0, sticky="we", padx=12, pady=6)
    include_spotlight_chk = ttk.Checkbutton(
        options, text="Copy the CoreSpotlight index (useful for residual fragments)", variable=include_spotlight_var
    )
    include_spotlight_chk.grid(
        row=0, column=0, sticky="w", padx=8, pady=2
    )
    include_cache_chk = ttk.Checkbutton(
        options, text="Copy the Notes cache (CloudKit / metadata)", variable=include_cache_var
    )
    include_cache_chk.grid(
        row=1, column=0, sticky="w", padx=8, pady=2
    )
    run_wal_chk = ttk.Checkbutton(options, text="Run WAL isolation (most effective right after deletion)", variable=run_wal_var)
    run_wal_chk.grid(
        row=2, column=0, sticky="w", padx=8, pady=2
    )
    run_query_chk = ttk.Checkbutton(options, text="Run database queries (ghost records)", variable=run_query_var)
    run_query_chk.grid(
        row=3, column=0, sticky="w", padx=8, pady=2
    )
    run_carve_chk = ttk.Checkbutton(options, text="Run gzip carving (slower, but deeper)", variable=run_carve_var)
    run_carve_chk.grid(
        row=4, column=0, sticky="w", padx=8, pady=2
    )
    run_recover_chk = ttk.Checkbutton(
        options, text="Run sqlite3 .recover (slower, but potentially more complete)", variable=run_recover_var
    )
    run_recover_chk.grid(
        row=5, column=0, sticky="w", padx=8, pady=2
    )
    run_plugins_chk = ttk.Checkbutton(
        options, text="Run external tools from plugins.json", variable=run_plugins_var
    )
    run_plugins_chk.grid(
        row=6, column=0, sticky="w", padx=8, pady=2
    )
    run_protobuf_chk = ttk.Checkbutton(
        options, text="Parse ZICNOTEDATA protobuf payloads", variable=run_protobuf_var
    )
    run_protobuf_chk.grid(
        row=7, column=0, sticky="w", padx=8, pady=2
    )
    run_spotlight_parse_chk = ttk.Checkbutton(
        options, text="Inspect CoreSpotlight metadata deeply", variable=run_spotlight_parse_var
    )
    run_spotlight_parse_chk.grid(
        row=8, column=0, sticky="w", padx=8, pady=2
    )
    report_chk = ttk.Checkbutton(options, text="Generate an HTML report", variable=report_var)
    report_chk.grid(
        row=9, column=0, sticky="w", padx=8, pady=2
    )
    verify_chk = ttk.Checkbutton(options, text="Run one-shot hit verification (Top 10 preview)", variable=verify_var)
    verify_chk.grid(
        row=10, column=0, sticky="w", padx=8, pady=2
    )
    verify_deep_chk = ttk.Checkbutton(options, text="Enable deep scanning (slower, but more complete)", variable=verify_deep_var)
    verify_deep_chk.grid(
        row=11, column=0, sticky="w", padx=8, pady=2
    )
    verify_deep_all_chk = ttk.Checkbutton(
        options, text="Use full deep-scan mode (includes more files)", variable=verify_deep_all_var
    )
    verify_deep_all_chk.grid(
        row=12, column=0, sticky="w", padx=8, pady=2
    )
    verify_match_all_chk = ttk.Checkbutton(options, text="Require every keyword to match (stricter)", variable=verify_match_all_var)
    verify_match_all_chk.grid(
        row=13, column=0, sticky="w", padx=8, pady=2
    )
    verify_fuzzy_chk = ttk.Checkbutton(options, text="Enable fuzzy matching (typo tolerant)", variable=verify_fuzzy_var)
    verify_fuzzy_chk.grid(
        row=14, column=0, sticky="w", padx=8, pady=2
    )

    tuning = ttk.Labelframe(content, text="Advanced tuning")
    tuning.grid(row=3, column=0, sticky="we", padx=12, pady=6)
    tuning.columnconfigure(1, weight=1)
    tuning.columnconfigure(3, weight=1)
    ttk.Label(tuning, text="Maximum report items (Top N)").grid(row=0, column=0, sticky="w", padx=8, pady=4)
    report_max_items_entry = ttk.Entry(
        tuning, textvariable=report_max_items_var, width=8, validate="key", validatecommand=validate_int_cmd
    )
    report_max_items_entry.grid(row=0, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(tuning, text="Maximum carve hits").grid(row=0, column=2, sticky="w", padx=8, pady=4)
    carve_max_hits_entry = ttk.Entry(
        tuning, textvariable=carve_max_hits_var, width=8, validate="key", validatecommand=validate_int_cmd
    )
    carve_max_hits_entry.grid(row=0, column=3, sticky="w", padx=6, pady=4)

    ttk.Label(tuning, text="Minimum carve readability ratio (0-1)").grid(row=1, column=0, sticky="w", padx=8, pady=4)
    carve_min_ratio_entry = ttk.Entry(
        tuning, textvariable=carve_min_ratio_var, width=8, validate="key", validatecommand=validate_float_cmd
    )
    carve_min_ratio_entry.grid(row=1, column=1, sticky="w", padx=6, pady=4)

    ttk.Label(tuning, text="Verification Top count").grid(row=2, column=0, sticky="w", padx=8, pady=4)
    verify_top_entry = ttk.Entry(
        tuning, textvariable=verify_top_var, width=8, validate="key", validatecommand=validate_int_cmd
    )
    verify_top_entry.grid(row=2, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(tuning, text="Preview length (characters)").grid(row=2, column=2, sticky="w", padx=8, pady=4)
    verify_preview_entry = ttk.Entry(
        tuning, textvariable=verify_preview_var, width=8, validate="key", validatecommand=validate_int_cmd
    )
    verify_preview_entry.grid(row=2, column=3, sticky="w", padx=6, pady=4)

    ttk.Label(tuning, text="Maximum deep-scan file size (MB, 0 = unlimited)").grid(row=3, column=0, sticky="w", padx=8, pady=4)
    verify_deep_max_mb_entry = ttk.Entry(
        tuning, textvariable=verify_deep_max_mb_var, width=8, validate="key", validatecommand=validate_int_cmd
    )
    verify_deep_max_mb_entry.grid(row=3, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(tuning, text="Maximum deep-scan hits per file").grid(row=3, column=2, sticky="w", padx=8, pady=4)
    verify_deep_max_hits_entry = ttk.Entry(
        tuning, textvariable=verify_deep_max_hits_var, width=8, validate="key", validatecommand=validate_int_cmd
    )
    verify_deep_max_hits_entry.grid(row=3, column=3, sticky="w", padx=6, pady=4)

    ttk.Separator(tuning, orient="horizontal").grid(row=4, column=0, columnspan=4, sticky="we", padx=6, pady=6)
    ttk.Label(tuning, text="Maximum Spotlight file count").grid(row=5, column=0, sticky="w", padx=8, pady=4)
    spotlight_max_files_entry = ttk.Entry(
        tuning, textvariable=spotlight_parse_max_files_var, width=10, validate="key", validatecommand=validate_int_cmd
    )
    spotlight_max_files_entry.grid(row=5, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(tuning, text="Maximum Spotlight file size (bytes)").grid(row=5, column=2, sticky="w", padx=8, pady=4)
    spotlight_max_bytes_entry = ttk.Entry(
        tuning, textvariable=spotlight_parse_max_bytes_var, width=12, validate="key", validatecommand=validate_int_cmd
    )
    spotlight_max_bytes_entry.grid(row=5, column=3, sticky="w", padx=6, pady=4)

    ttk.Label(tuning, text="Minimum Spotlight string length").grid(row=6, column=0, sticky="w", padx=8, pady=4)
    spotlight_min_len_entry = ttk.Entry(
        tuning, textvariable=spotlight_parse_min_len_var, width=10, validate="key", validatecommand=validate_int_cmd
    )
    spotlight_min_len_entry.grid(row=6, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(tuning, text="Maximum Spotlight characters per file").grid(row=6, column=2, sticky="w", padx=8, pady=4)
    spotlight_max_chars_entry = ttk.Entry(
        tuning, textvariable=spotlight_parse_max_chars_var, width=12, validate="key", validatecommand=validate_int_cmd
    )
    spotlight_max_chars_entry.grid(row=6, column=3, sticky="w", padx=6, pady=4)

    ttk.Label(tuning, text="Maximum Spotlight SQLite rows").grid(row=7, column=0, sticky="w", padx=8, pady=4)
    spotlight_max_rows_entry = ttk.Entry(
        tuning, textvariable=spotlight_parse_max_rows_var, width=10, validate="key", validatecommand=validate_int_cmd
    )
    spotlight_max_rows_entry.grid(row=7, column=1, sticky="w", padx=6, pady=4)

    ttk.Separator(tuning, orient="horizontal").grid(row=8, column=0, columnspan=4, sticky="we", padx=6, pady=6)
    ttk.Label(tuning, text="Ignore freelist during recover").grid(row=9, column=0, sticky="w", padx=8, pady=4)
    recover_ignore_chk = ttk.Checkbutton(tuning, text="Enable", variable=recover_ignore_freelist_var)
    recover_ignore_chk.grid(row=9, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(tuning, text="lost_and_found table name").grid(row=9, column=2, sticky="w", padx=8, pady=4)
    recover_lost_entry = ttk.Entry(tuning, textvariable=recover_lost_and_found_var, width=14)
    recover_lost_entry.grid(row=9, column=3, sticky="w", padx=6, pady=4)

    ttk.Label(tuning, text="Plugin config path (optional)").grid(row=10, column=0, sticky="w", padx=8, pady=4)
    plugins_config_entry = ttk.Entry(tuning, textvariable=plugins_config_var)
    plugins_config_entry.grid(row=10, column=1, columnspan=2, sticky="we", padx=6, pady=4)
    plugins_enable_all_chk = ttk.Checkbutton(tuning, text="Force-run all plugins", variable=plugins_enable_all_var)
    plugins_enable_all_chk.grid(row=10, column=3, sticky="w", padx=6, pady=4)

    ttk.Separator(tuning, orient="horizontal").grid(row=11, column=0, columnspan=4, sticky="we", padx=6, pady=6)
    ttk.Label(tuning, text="Fuzzy-match threshold (0-1)").grid(row=12, column=0, sticky="w", padx=8, pady=4)
    verify_fuzzy_threshold_entry = ttk.Entry(
        tuning, textvariable=verify_fuzzy_threshold_var, width=8, validate="key", validatecommand=validate_float_cmd
    )
    verify_fuzzy_threshold_entry.grid(row=12, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(tuning, text="Fuzzy-match boost factor").grid(row=12, column=2, sticky="w", padx=8, pady=4)
    verify_fuzzy_boost_entry = ttk.Entry(
        tuning, textvariable=verify_fuzzy_boost_var, width=8, validate="key", validatecommand=validate_float_cmd
    )
    verify_fuzzy_boost_entry.grid(row=12, column=3, sticky="w", padx=6, pady=4)
    ttk.Label(tuning, text="Maximum fuzzy-match comparison length").grid(row=13, column=0, sticky="w", padx=8, pady=4)
    verify_fuzzy_max_len_entry = ttk.Entry(
        tuning, textvariable=verify_fuzzy_max_len_var, width=8, validate="key", validatecommand=validate_int_cmd
    )
    verify_fuzzy_max_len_entry.grid(row=13, column=1, sticky="w", padx=6, pady=4)

    presets = ttk.Labelframe(content, text="Quick presets")
    presets.grid(row=4, column=0, sticky="we", padx=12, pady=6)
    ttk.Label(presets, text="Quickly switch common configurations without touching the original data.").grid(
        row=0, column=0, columnspan=3, sticky="w", padx=8, pady=4
    )

    def apply_preset(mode: str) -> None:
        if mode == "recommended":
            include_spotlight_var.set(True)
            include_cache_var.set(True)
            run_wal_var.set(True)
            run_query_var.set(True)
            run_carve_var.set(True)
            run_recover_var.set(False)
            run_plugins_var.set(False)
            run_protobuf_var.set(False)
            run_spotlight_parse_var.set(False)
            report_var.set(True)
            verify_var.set(True)
            verify_deep_var.set(True)
            verify_deep_all_var.set(True)
            verify_match_all_var.set(False)
            verify_fuzzy_var.set(True)
            report_max_items_var.set(50)
            carve_max_hits_var.set(200)
            carve_min_ratio_var.set(0.55)
            protobuf_max_notes_var.set(PROTOBUF_MAX_NOTES_DEFAULT)
            protobuf_max_zdata_mb_var.set(PROTOBUF_MAX_ZDATA_MB_DEFAULT)
            spotlight_parse_max_files_var.set(SPOTLIGHT_PARSE_MAX_FILES_DEFAULT)
            spotlight_parse_max_bytes_var.set(SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT)
            spotlight_parse_min_len_var.set(SPOTLIGHT_PARSE_MIN_STRING_LEN)
            spotlight_parse_max_chars_var.set(SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT)
            spotlight_parse_max_rows_var.set(SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT)
            verify_top_var.set(10)
            verify_preview_var.set(300)
            verify_deep_max_mb_var.set(0)
            verify_deep_max_hits_var.set(200)
            verify_fuzzy_threshold_var.set(0.72)
            verify_fuzzy_boost_var.set(6.0)
            verify_fuzzy_max_len_var.set(2000)
            recover_ignore_freelist_var.set(False)
            recover_lost_and_found_var.set("lost_and_found")
        elif mode == "fast":
            include_spotlight_var.set(True)
            include_cache_var.set(True)
            run_wal_var.set(True)
            run_query_var.set(True)
            run_carve_var.set(False)
            run_recover_var.set(False)
            run_plugins_var.set(False)
            run_protobuf_var.set(False)
            run_spotlight_parse_var.set(False)
            report_var.set(True)
            verify_var.set(False)
            verify_deep_var.set(False)
            verify_deep_all_var.set(False)
            verify_match_all_var.set(False)
            verify_fuzzy_var.set(False)
            carve_min_ratio_var.set(0.6)
            spotlight_parse_max_files_var.set(SPOTLIGHT_PARSE_MAX_FILES_DEFAULT)
            spotlight_parse_max_bytes_var.set(SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT)
            spotlight_parse_min_len_var.set(SPOTLIGHT_PARSE_MIN_STRING_LEN)
            spotlight_parse_max_chars_var.set(SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT)
            spotlight_parse_max_rows_var.set(SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT)
        elif mode == "deep":
            include_spotlight_var.set(True)
            include_cache_var.set(True)
            run_wal_var.set(True)
            run_query_var.set(True)
            run_carve_var.set(True)
            run_recover_var.set(True)
            run_plugins_var.set(False)
            run_protobuf_var.set(True)
            run_spotlight_parse_var.set(True)
            report_var.set(True)
            verify_var.set(True)
            verify_deep_var.set(True)
            verify_deep_all_var.set(True)
            verify_match_all_var.set(False)
            verify_fuzzy_var.set(True)
            carve_min_ratio_var.set(0.5)
            protobuf_max_notes_var.set(PROTOBUF_MAX_NOTES_DEFAULT)
            protobuf_max_zdata_mb_var.set(PROTOBUF_MAX_ZDATA_MB_DEFAULT)
            spotlight_parse_max_files_var.set(SPOTLIGHT_PARSE_MAX_FILES_DEFAULT)
            spotlight_parse_max_bytes_var.set(SPOTLIGHT_PARSE_MAX_BYTES_DEFAULT)
            spotlight_parse_min_len_var.set(SPOTLIGHT_PARSE_MIN_STRING_LEN)
            spotlight_parse_max_chars_var.set(SPOTLIGHT_PARSE_MAX_STRING_CHARS_DEFAULT)
            spotlight_parse_max_rows_var.set(SPOTLIGHT_PARSE_MAX_ROWS_PER_TABLE_DEFAULT)

    def apply_spotlight_preset(level: str) -> None:
        include_spotlight_var.set(True)
        run_spotlight_parse_var.set(True)
        if level == "fast":
            spotlight_parse_max_files_var.set(120)
            spotlight_parse_max_bytes_var.set(32 * 1024 * 1024)
            spotlight_parse_min_len_var.set(4)
            spotlight_parse_max_chars_var.set(60_000)
            spotlight_parse_max_rows_var.set(800)
        elif level == "deep":
            spotlight_parse_max_files_var.set(600)
            spotlight_parse_max_bytes_var.set(128 * 1024 * 1024)
            spotlight_parse_min_len_var.set(3)
            spotlight_parse_max_chars_var.set(250_000)
            spotlight_parse_max_rows_var.set(8000)

    ttk.Button(presets, text="Recommended", command=lambda: apply_preset("recommended")).grid(
        row=1, column=0, padx=8, pady=4, sticky="w"
    )
    ttk.Button(presets, text="Fast triage", command=lambda: apply_preset("fast")).grid(
        row=1, column=1, padx=8, pady=4, sticky="w"
    )
    ttk.Button(presets, text="Deep forensics", command=lambda: apply_preset("deep")).grid(
        row=1, column=2, padx=8, pady=4, sticky="w"
    )
    ttk.Button(presets, text="Spotlight fast", command=lambda: apply_spotlight_preset("fast")).grid(
        row=2, column=0, padx=8, pady=4, sticky="w"
    )
    ttk.Button(presets, text="Spotlight deep", command=lambda: apply_spotlight_preset("deep")).grid(
        row=2, column=1, padx=8, pady=4, sticky="w"
    )

    log_cfg = ttk.Labelframe(content, text="Logging")
    log_cfg.grid(row=5, column=0, sticky="we", padx=12, pady=6)
    log_cfg.columnconfigure(1, weight=1)
    log_cfg.columnconfigure(3, weight=1)
    log_to_file_chk = ttk.Checkbutton(log_cfg, text="Save logs to a file", variable=log_to_file_var)
    log_to_file_chk.grid(row=0, column=0, sticky="w", padx=8, pady=4)
    ttk.Label(log_cfg, text="Log level").grid(row=0, column=2, sticky="w", padx=8, pady=4)
    log_level_menu = ttk.Combobox(
        log_cfg,
        textvariable=log_level_var,
        values=["debug", "info", "warning", "error"],
        width=12,
        state="readonly",
    )
    log_level_menu.grid(row=0, column=3, sticky="w", padx=6, pady=4)
    ttk.Label(log_cfg, text="Log file (auto = output directory)").grid(row=1, column=0, sticky="w", padx=8, pady=4)
    log_file_entry = ttk.Entry(log_cfg, textvariable=log_file_var)
    log_file_entry.grid(row=1, column=1, sticky="we", padx=6, pady=4)
    log_append_chk = ttk.Checkbutton(log_cfg, text="Append to the file", variable=log_append_var)
    log_append_chk.grid(row=1, column=2, sticky="w", padx=8, pady=4)
    log_json_chk = ttk.Checkbutton(log_cfg, text="JSON format", variable=log_json_var)
    log_json_chk.grid(
        row=1, column=3, sticky="w", padx=6, pady=4
    )
    ttk.Label(log_cfg, text="Log size limit (bytes)").grid(row=2, column=0, sticky="w", padx=8, pady=4)
    log_max_bytes_entry = ttk.Entry(
        log_cfg, textvariable=log_max_bytes_var, width=12, validate="key", validatecommand=validate_int_cmd
    )
    log_max_bytes_entry.grid(row=2, column=1, sticky="w", padx=6, pady=4)
    ttk.Label(log_cfg, text="Backup count").grid(row=2, column=2, sticky="w", padx=8, pady=4)
    log_backup_count_entry = ttk.Entry(
        log_cfg, textvariable=log_backup_count_var, width=12, validate="key", validatecommand=validate_int_cmd
    )
    log_backup_count_entry.grid(row=2, column=3, sticky="w", padx=6, pady=4)
    ttk.Label(log_cfg, text="Timestamp format").grid(row=3, column=0, sticky="w", padx=8, pady=4)
    log_time_entry = ttk.Entry(log_cfg, textvariable=log_time_format_var)
    log_time_entry.grid(row=3, column=1, sticky="we", padx=6, pady=4)
    log_utc_chk = ttk.Checkbutton(log_cfg, text="Use UTC", variable=log_utc_var)
    log_utc_chk.grid(
        row=3, column=2, sticky="w", padx=8, pady=4
    )
    ttk.Label(log_cfg, text="Console log level").grid(row=3, column=3, sticky="w", padx=8, pady=4)
    log_console_menu = ttk.Combobox(
        log_cfg,
        textvariable=log_console_level_var,
        values=["debug", "info", "warning", "error"],
        width=12,
        state="readonly",
    )
    log_console_menu.grid(row=4, column=3, sticky="w", padx=6, pady=4)

    action_row = ttk.Frame(content)
    action_row.grid(row=6, column=0, sticky="we", padx=12, pady=(6, 12))
    action_row.columnconfigure(3, weight=1)
    start_btn = ttk.Button(action_row, text="Start recovery", command=start)
    start_btn.grid(row=0, column=0, sticky="w")
    ttk.Button(action_row, text="Open output directory", command=open_output_dir).grid(row=0, column=1, sticky="w", padx=8)
    ttk.Button(action_row, text="Reset settings", command=reset_form).grid(row=0, column=2, sticky="w", padx=8)
    ttk.Label(action_row, textvariable=status_var).grid(row=0, column=3, sticky="w", padx=10)
    ttk.Label(action_row, textvariable=summary_var).grid(row=1, column=0, columnspan=4, sticky="w", pady=4)

    log_title = ttk.Frame(log_host)
    log_title.pack(fill="x", padx=12, pady=(12, 6))
    ttk.Label(log_title, text="Run log (wait until all stages finish)").pack(side="left")
    ttk.Button(
        log_title,
        text="Clear log",
        command=lambda: (log_box.configure(state="normal"), log_box.delete("1.0", "end"), log_box.configure(state="disabled")),
    ).pack(side="right")
    ttk.Button(log_title, text="Copy log", command=copy_log).pack(side="right", padx=6)

    progress = ttk.Progressbar(log_host, mode="indeterminate")
    progress.pack(fill="x", padx=12)

    log_frame = ttk.Frame(log_host)
    log_frame.pack(fill="both", expand=True, padx=12, pady=8)
    log_scroll = ttk.Scrollbar(log_frame, orient="vertical")
    log_box = tk.Text(log_frame, height=14, wrap="word", yscrollcommand=log_scroll.set, state="disabled")
    log_scroll.config(command=log_box.yview)
    log_box.pack(side="left", fill="both", expand=True)
    log_scroll.pack(side="right", fill="y")

    def set_widget_state(widget: tk.Widget, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        try:
            widget.configure(state=state)
        except tk.TclError:
            return

    def update_states(*_args: object) -> None:
        report_on = report_var.get()
        verify_on = verify_var.get()
        deep_on = verify_on and verify_deep_var.get()
        fuzzy_on = verify_on and verify_fuzzy_var.get()
        recover_on = run_recover_var.get()
        log_on = log_to_file_var.get()

        set_widget_state(report_max_items_entry, report_on)
        set_widget_state(verify_top_entry, verify_on)
        set_widget_state(verify_preview_entry, verify_on)
        set_widget_state(verify_deep_max_mb_entry, deep_on)
        set_widget_state(verify_deep_max_hits_entry, deep_on)
        set_widget_state(verify_fuzzy_threshold_entry, fuzzy_on)
        set_widget_state(verify_fuzzy_boost_entry, fuzzy_on)
        set_widget_state(verify_fuzzy_max_len_entry, fuzzy_on)
        set_widget_state(recover_ignore_chk, recover_on)
        set_widget_state(recover_lost_entry, recover_on)
        set_widget_state(plugins_config_entry, run_plugins_var.get())
        set_widget_state(plugins_enable_all_chk, run_plugins_var.get())
        spotlight_on = run_spotlight_parse_var.get()
        set_widget_state(spotlight_max_files_entry, spotlight_on)
        set_widget_state(spotlight_max_bytes_entry, spotlight_on)
        set_widget_state(spotlight_min_len_entry, spotlight_on)
        set_widget_state(spotlight_max_chars_entry, spotlight_on)
        set_widget_state(spotlight_max_rows_entry, spotlight_on)
        set_widget_state(verify_deep_chk, verify_on)
        set_widget_state(verify_deep_all_chk, deep_on)
        set_widget_state(verify_match_all_chk, verify_on)
        set_widget_state(verify_fuzzy_chk, verify_on)
        set_widget_state(log_level_menu, log_on)
        set_widget_state(log_file_entry, log_on)
        set_widget_state(log_append_chk, log_on)
        set_widget_state(log_max_bytes_entry, log_on)
        set_widget_state(log_backup_count_entry, log_on)
        set_widget_state(log_time_entry, log_on)
        set_widget_state(log_utc_chk, log_on)
        set_widget_state(log_json_chk, log_on)
        set_widget_state(log_console_menu, log_on)

        steps = []
        if include_spotlight_var.get():
            steps.append("Spotlight")
        if include_cache_var.get():
            steps.append("Cache")
        if run_wal_var.get():
            steps.append("WAL")
        if run_query_var.get():
            steps.append("Query")
        if run_carve_var.get():
            steps.append("Carve")
        if run_recover_var.get():
            steps.append("Recover")
        if run_protobuf_var.get():
            steps.append("Protobuf")
        if run_spotlight_parse_var.get():
            steps.append("SpotlightParse")
        if run_plugins_var.get():
            steps.append("Plugins")
        if report_var.get():
            steps.append("Report")
        if verify_var.get():
            steps.append("Verify")
        if verify_var.get() and verify_deep_var.get():
            steps.append("DeepScan")
        if verify_var.get() and verify_fuzzy_var.get():
            steps.append("Fuzzy")
        speed = estimate_speed_label()
        summary = "Selected steps: " + (", ".join(steps) if steps else "none") + f" | {speed}"
        summary_var.set(summary)

    for var in (
        include_spotlight_var,
        include_cache_var,
        run_wal_var,
        run_query_var,
        run_carve_var,
        run_recover_var,
        run_protobuf_var,
        run_spotlight_parse_var,
        spotlight_parse_max_files_var,
        spotlight_parse_max_bytes_var,
        spotlight_parse_min_len_var,
        spotlight_parse_max_chars_var,
        spotlight_parse_max_rows_var,
        run_plugins_var,
        report_var,
        verify_var,
        verify_deep_var,
        verify_deep_all_var,
        verify_match_all_var,
        verify_fuzzy_var,
        log_to_file_var,
        log_level_var,
        log_file_var,
        log_append_var,
        log_max_bytes_var,
        log_backup_count_var,
        log_time_format_var,
        log_utc_var,
        log_json_var,
        log_console_level_var,
    ):
        var.trace_add("write", update_states)
    update_states()

    root.after(100, log_pump)
    root.mainloop()


# =============================================================================
