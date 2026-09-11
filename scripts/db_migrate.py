#!/usr/bin/env python3
"""Apply Alembic migrations (fieldbrain_db_migrate tool)."""

from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config

from _db_lib import SCHEMA_VERSION, build_database_url, read_applied_schema_version, reset_engine
from _json_out import emit, emit_error
from services.migrate_lock import migration_advisory_lock


def alembic_config() -> Config:
    scripts_dir = Path(__file__).resolve().parent
    cfg = Config(str(scripts_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(scripts_dir / "alembic"))
    cfg.set_main_option("sqlalchemy.url", build_database_url())
    return cfg


def apply_migrations() -> int:
    """Upgrade to head under advisory lock; return applied schema version."""
    reset_engine()
    from _db_lib import get_engine

    engine = get_engine()
    with migration_advisory_lock(engine):
        command.upgrade(alembic_config(), "head")
    reset_engine()
    applied = read_applied_schema_version()
    if applied != SCHEMA_VERSION:
        raise RuntimeError(
            f"Migration finished but schema version is {applied}, expected {SCHEMA_VERSION}."
        )
    return int(applied)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Report current schema version without migrating",
    )
    args = parser.parse_args()

    reset_engine()
    url = build_database_url()

    if args.check_only:
        try:
            applied = read_applied_schema_version()
        except Exception as exc:
            emit_error(f"Could not read schema version: {exc}", database_url_host=url)
        emit(
            {
                "ok": True,
                "applied_schema_version": applied,
                "expected_schema_version": SCHEMA_VERSION,
                "operator_chat": f"Applied schema version: {applied}; package expects {SCHEMA_VERSION}.",
            }
        )

    try:
        applied = apply_migrations()
    except Exception as exc:
        emit_error(f"Migration failed: {exc}")

    emit(
        {
            "ok": True,
            "migrated": True,
            "applied_schema_version": applied,
            "expected_schema_version": SCHEMA_VERSION,
            "operator_chat": f"FieldBrain database migrated to schema version {applied}.",
        }
    )


if __name__ == "__main__":
    main()
