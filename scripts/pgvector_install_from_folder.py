#!/usr/bin/env python3
"""Copy pgvector from operator folder/zip, then enable extension in FieldBrain DB."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from _db_lib import load_database_config, run_health_check
from _json_out import emit, emit_error
from services.pgvector_windows import (
    guess_pgroot_for_major,
    install_pgvector_files,
    layman_pgvector_steps,
    resolve_source_dir,
    windows_install_status,
)


def _parse_script_json(stdout: str) -> dict:
    trimmed = stdout.strip()
    if not trimmed:
        return {"ok": False, "error": "empty output"}
    for line in reversed(trimmed.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return {"ok": False, "error": trimmed}


def _run_enable(args: argparse.Namespace, admin_password: str) -> dict:
    script = Path(__file__).resolve().parent / "pgvector_enable.py"
    cmd = [
        sys.executable,
        str(script),
        "--admin-user",
        args.admin_user,
        "--admin-password",
        admin_password,
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--database",
        args.database,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    parsed = _parse_script_json(proc.stdout or "")
    if parsed.get("ok") is False and proc.stderr:
        parsed.setdefault("error", proc.stderr.strip())
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="", help="Folder or .zip with pgvector files (local Postgres only)")
    parser.add_argument("--admin-user", default="postgres")
    parser.add_argument("--admin-password", default="")
    parser.add_argument("--host", default="")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--database", default="")
    parser.add_argument("--skip-file-copy", action="store_true", help="Only CREATE EXTENSION (remote server)")
    args = parser.parse_args()

    admin_password = (args.admin_password or os.environ.get("SYLO_FIELDBRAIN_BOOTSTRAP_ADMIN_PASSWORD") or "").strip()
    if not admin_password:
        emit_error("Postgres superuser password is required (not saved).")

    cfg = load_database_config() or {}
    host = (args.host or str(cfg.get("host") or "localhost")).strip()
    port = args.port or int(cfg.get("port") or 5432)
    database = (args.database or str(cfg.get("database") or "fieldbrain")).strip()
    args.host = host
    args.port = port
    args.database = database

    health = run_health_check()
    if health.get("postgres_connected") is not True:
        emit_error(health.get("postgres_error", "Connect to Postgres first (Test connection)."))

    major = health.get("postgres_major")
    if isinstance(major, str) and major.isdigit():
        major = int(major)
    install = windows_install_status(major if isinstance(major, int) else None)
    db_mode = "remote" if host not in ("localhost", "127.0.0.1") else str(
        health.get("db_mode") or "local"
    )

    copy_steps: list[str] = []
    if not args.skip_file_copy and db_mode == "local":
        source = (args.source or "").strip()
        if not source:
            emit_error(
                "Select the extracted pgvector folder (or .zip) first.",
                pgvector_setup=layman_pgvector_steps(
                    major if isinstance(major, int) else None,
                    files_installed=bool(install.get("vector_files_installed")),
                    db_mode=db_mode,
                ),
            )
        pgroot = guess_pgroot_for_major(major) if isinstance(major, int) else None
        if pgroot is None:
            emit_error("Could not find PostgreSQL install folder on this PC.")
        source_dir, tmp, err = resolve_source_dir(source)
        if err or source_dir is None:
            emit_error(err or "Invalid pgvector source path")
        try:
            copy_result = install_pgvector_files(source_dir, pgroot)
        finally:
            if tmp is not None:
                tmp.cleanup()
        if not copy_result.get("ok"):
            emit_error(
                copy_result.get("error", "File copy failed"),
                **{
                    **install,
                    "needs_elevation": copy_result.get("needs_elevation"),
                    "pgroot": copy_result.get("pgroot") or install.get("pgroot"),
                    "source_dir": str(source_dir),
                },
            )
        copy_steps.append(f"Installed pgvector files into {copy_result.get('pgroot')}")
        install = windows_install_status(major if isinstance(major, int) else None)

    enable_result = _run_enable(args, admin_password)
    if enable_result.get("ok") is False:
        emit_error(
            enable_result.get("error", "Enable failed"),
            pgvector_setup=enable_result.get("pgvector_setup"),
            **install,
        )

    lines = [*copy_steps]
    if enable_result.get("operator_chat"):
        lines.append(str(enable_result["operator_chat"]))
    emit({**enable_result, "operator_chat": "\n".join(lines), **install})


if __name__ == "__main__":
    main()
