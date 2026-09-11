#!/usr/bin/env python3
"""Install pgvector files from an operator-selected folder or zip."""

from __future__ import annotations

import argparse
import json
import os

from _json_out import emit, emit_error
from services.pgvector_windows import (
    guess_pgroot_for_major,
    install_pgvector_files,
    resolve_source_dir,
    windows_install_status,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Folder or .zip containing pgvector files")
    parser.add_argument("--postgres-major", type=int, default=0)
    parser.add_argument("--pgroot", default="", help="Override PostgreSQL install directory")
    args = parser.parse_args()

    major = args.postgres_major or int(os.environ.get("SYLO_FIELDBRAIN_POSTGRES_MAJOR") or 0) or None
    pgroot_raw = (args.pgroot or os.environ.get("SYLO_FIELDBRAIN_PGROOT") or "").strip()
    if pgroot_raw:
        from pathlib import Path

        pgroot = Path(pgroot_raw)
    elif major:
        pgroot = guess_pgroot_for_major(major)
    else:
        pgroot = None

    if pgroot is None:
        emit_error("Could not determine PostgreSQL install folder. Connect to Postgres and retry.")

    source_dir, tmp, err = resolve_source_dir(args.source)
    if err or source_dir is None:
        emit_error(err or "Invalid source path")

    try:
        result = install_pgvector_files(source_dir, pgroot)
    finally:
        if tmp is not None:
            tmp.cleanup()

    status = windows_install_status(major)
    payload = {**result, **status}
    if result.get("ok"):
        emit(
            {
                **payload,
                "operator_chat": (
                    f"Copied pgvector files into {result.get('pgroot')}.\n"
                    "Next: Enable semantic search in FieldBrain Settings."
                ),
            }
        )
    emit_error(result.get("error", "Install failed"), **payload)


if __name__ == "__main__":
    main()
