#!/usr/bin/env python3
"""Apply Alembic migrations when the shared DB is behind this package (startup + Settings button)."""

from __future__ import annotations

import argparse

from sqlalchemy import text

from _db_lib import SCHEMA_VERSION, get_engine, read_applied_schema_version, reset_engine
from _json_out import emit, emit_error
from db_migrate import apply_migrations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report whether migration would run without changing the database",
    )
    args = parser.parse_args()

    reset_engine()
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        emit(
            {
                "ok": True,
                "migrated": False,
                "skipped": True,
                "reason": "not_connected",
                "error": str(exc),
                "operator_chat": f"Auto-migrate skipped: could not connect to Postgres ({exc}).",
            }
        )
        return

    try:
        applied = read_applied_schema_version()
    except Exception as exc:
        if args.dry_run:
            emit_error(f"Could not read schema version: {exc}")
        applied = None

    if applied == SCHEMA_VERSION:
        emit(
            {
                "ok": True,
                "migrated": False,
                "already_current": True,
                "applied_schema_version": applied,
                "expected_schema_version": SCHEMA_VERSION,
                "operator_chat": f"Database already at schema version {applied}.",
            }
        )
        return

    if applied is not None and applied > SCHEMA_VERSION:
        emit_error(
            f"Database schema {applied} is newer than this Sylo build ({SCHEMA_VERSION}). "
            "Update Sylo on this machine (git pull / reinstall).",
            applied_schema_version=applied,
            expected_schema_version=SCHEMA_VERSION,
        )

    if args.dry_run:
        emit(
            {
                "ok": True,
                "migrated": False,
                "would_migrate": True,
                "applied_schema_version": applied,
                "expected_schema_version": SCHEMA_VERSION,
                "operator_chat": (
                    f"Database at version {applied}; package expects {SCHEMA_VERSION}. "
                    "Migration runs on Sylo startup or via Apply database updates in Settings."
                ),
            }
        )
        return

    try:
        new_version = apply_migrations()
    except Exception as exc:
        emit_error(f"Migration failed: {exc}")

    emit(
        {
            "ok": True,
            "migrated": True,
            "applied_schema_version": new_version,
            "expected_schema_version": SCHEMA_VERSION,
            "operator_chat": f"FieldBrain database updated to schema version {new_version}.",
        }
    )


if __name__ == "__main__":
    main()
