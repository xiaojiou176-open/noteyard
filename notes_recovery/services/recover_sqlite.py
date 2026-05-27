from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from notes_recovery.io import ensure_dir
from notes_recovery.logging import eprint
from notes_recovery.core.text_bundle import flatten_safe_name, shorten_name_if_needed


def get_sqlite3_path() -> Path:
    system_sqlite = Path("/usr/bin/sqlite3")
    if system_sqlite.exists():
        return system_sqlite
    found = shutil.which("sqlite3")
    if found:
        return Path(found)
    raise RuntimeError("sqlite3 was not found. Install the sqlite3 CLI first.")


def sqlite_recover(
    db_path: Path,
    out_dir: Path,
    ignore_freelist: bool,
    lost_and_found: str,
    *,
    sqlite3_path_resolver=get_sqlite3_path,
    subprocess_module=subprocess,
    eprint_fn=eprint,
) -> Path:
    if not db_path.exists():
        raise RuntimeError(f"Database does not exist: {db_path}")
    ensure_dir(out_dir)
    sqlite3_path = sqlite3_path_resolver()
    sql_path = out_dir / f"{db_path.stem}_recover.sql"
    out_db_path = out_dir / f"{db_path.stem}_recovered.sqlite"

    options = []
    if ignore_freelist:
        options.append("--ignore-freelist")
    if lost_and_found:
        options.extend(["--lost-and-found", lost_and_found])
    option_str = " ".join(options)
    recover_cmd = f".recover {option_str}".strip()

    try:
        with sql_path.open("w", encoding="utf-8") as out_sql:
            completed = subprocess_module.run(
                [str(sqlite3_path), str(db_path)],
                input=recover_cmd + "\n",
                check=True,
                stdout=out_sql,
                stderr=subprocess_module.PIPE,
                text=True,
            )
            if completed.stderr:
                eprint_fn(completed.stderr.strip())
    except subprocess_module.CalledProcessError as exc:
        raise RuntimeError(f"Failed to write recovered database SQL: {exc.stderr}")
    except Exception as exc:
        raise RuntimeError(f"Failed to create recovered database: {out_db_path} -> {exc}")

    try:
        with sql_path.open("r", encoding="utf-8") as fin:
            completed = subprocess_module.run(
                [str(sqlite3_path), str(out_db_path)],
                stdin=fin,
                check=True,
                stdout=subprocess_module.PIPE,
                stderr=subprocess_module.PIPE,
                text=True,
            )
            if completed.stderr:
                eprint_fn(completed.stderr.strip())
    except subprocess_module.CalledProcessError as exc:
        raise RuntimeError(f"Failed to materialize recovered database: {exc.stderr}")
    except Exception as exc:
        raise RuntimeError(f"Failed to create recovered database: {out_db_path} -> {exc}")

    print(f"Recovered database written: {out_db_path}")
    return out_db_path


def sanitize_label(label: str) -> str:
    if not label:
        return "unknown"
    cleaned = label.replace("/", "__").replace("\\", "__")
    cleaned = flatten_safe_name(cleaned)
    cleaned = shorten_name_if_needed(cleaned, 160)
    return cleaned
