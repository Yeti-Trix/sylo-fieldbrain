#!/usr/bin/env python3
"""One-time Postgres bootstrap: create FieldBrain role + database, pgvector, migrate."""

from __future__ import annotations

import argparse
import os
import urllib.parse

from sqlalchemy import create_engine, text

from _db_lib import SCHEMA_VERSION, read_applied_schema_version, reset_engine
from _json_out import emit, emit_error
from db_migrate import alembic_config


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _build_url(host: str, port: int, database: str, username: str, password: str) -> str:
    safe_password = urllib.parse.quote_plus(password) if password else ""
    auth = f"{urllib.parse.quote_plus(username)}:{safe_password}@" if safe_password else f"{urllib.parse.quote_plus(username)}@"
    return f"postgresql://{auth}{host}:{port}/{database}"


def _role_exists(conn, role: str) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
        {"name": role},
    ).fetchone()
    return row is not None


def _database_exists(conn, database: str) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :name"),
        {"name": database},
    ).fetchone()
    return row is not None


def _try_pgvector(app_url: str) -> tuple[bool, str | None]:
    engine = create_engine(app_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
        if row:
            return True, str(row[0])
        return False, "CREATE EXTENSION succeeded but vector not visible"
    except Exception as exc:
        return False, str(exc)
    finally:
        engine.dispose()


def _run_migrate(app_url: str) -> tuple[int | None, str | None]:
    from alembic import command

    os.environ["SYLO_FIELDBRAIN_DATABASE_URL"] = app_url
    reset_engine()
    try:
        command.upgrade(alembic_config(), "head")
    except Exception as exc:
        return None, str(exc)
    reset_engine()
    try:
        applied = read_applied_schema_version()
    except Exception as exc:
        return None, f"Migration ran but schema version unreadable: {exc}"
    if applied != SCHEMA_VERSION:
        return applied, f"Expected schema {SCHEMA_VERSION}, got {applied}"
    return applied, None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-user", default="postgres")
    parser.add_argument("--admin-password", default="")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--app-database", default="fieldbrain")
    parser.add_argument("--app-username", default="fieldbrain")
    parser.add_argument("--app-password", default="fieldbrain")
    parser.add_argument("--skip-migrate", action="store_true")
    args = parser.parse_args()

    admin_password = (args.admin_password or os.environ.get("SYLO_FIELDBRAIN_BOOTSTRAP_ADMIN_PASSWORD") or "").strip()
    if not admin_password:
        emit_error("Postgres superuser password is required for bootstrap (not stored after this run).")

    host = args.host.strip() or "localhost"
    port = int(args.port)
    app_db = args.app_database.strip() or "fieldbrain"
    app_user = args.app_username.strip() or "fieldbrain"
    app_password = args.app_password if args.app_password is not None else "fieldbrain"

    admin_user = args.admin_user.strip() or "postgres"
    admin_url = _build_url(host, port, "postgres", admin_user, admin_password)
    steps: list[str] = []

    try:
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
        with admin_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        steps.append(f"Connected as superuser {admin_user}@{host}:{port}")
    except Exception as exc:
        emit_error(
            f"Could not connect as Postgres superuser: {exc}",
            hint="Use the password you set at PostgreSQL install (or reset via pg_hba.conf trust).",
        )

    try:
        with admin_engine.connect() as conn:
            if _role_exists(conn, app_user):
                conn.execute(
                    text(
                        f"ALTER USER {_quote_ident(app_user)} "
                        f"WITH PASSWORD {_quote_literal(app_password)}"
                    )
                )
                steps.append(f"Role {app_user} already existed — password updated")
            else:
                conn.execute(
                    text(
                        f"CREATE USER {_quote_ident(app_user)} "
                        f"WITH PASSWORD {_quote_literal(app_password)}"
                    )
                )
                steps.append(f"Created role {app_user}")

            if _database_exists(conn, app_db):
                steps.append(f"Database {app_db} already existed — skipped CREATE DATABASE")
            else:
                conn.execute(
                    text(
                        f"CREATE DATABASE {_quote_ident(app_db)} "
                        f"OWNER {_quote_ident(app_user)}"
                    )
                )
                steps.append(f"Created database {app_db}")
    except Exception as exc:
        admin_engine.dispose()
        emit_error(f"Bootstrap DDL failed: {exc}", steps=steps)
    admin_engine.dispose()

    app_url = _build_url(host, port, app_db, app_user, app_password)
    pgvector_ok, pgvector_detail = _try_pgvector(app_url)
    if pgvector_ok:
        steps.append(f"pgvector enabled ({pgvector_detail})")
    else:
        steps.append(
            "pgvector not installed — semantic search unavailable until you install pgvector "
            f"and run CREATE EXTENSION vector ({pgvector_detail})"
        )

    applied_version: int | None = None
    if not args.skip_migrate:
        applied_version, migrate_err = _run_migrate(app_url)
        if migrate_err:
            emit_error(
                migrate_err,
                steps=steps,
                pgvector_ok=pgvector_ok,
                app_database=app_db,
                app_username=app_user,
            )
        steps.append(f"Migrated to schema version {applied_version}")

    lines = [
        f"FieldBrain database ready: {app_user}@{host}:{port}/{app_db}",
        *steps,
        "Superuser password was not saved. Runtime uses the FieldBrain user only.",
    ]
    if not pgvector_ok:
        lines.append(
            "Optional semantic search: download pgvector, browse to the folder in FieldBrain Settings, "
            "then Install pgvector & enable semantic search."
        )

    emit(
        {
            "ok": True,
            "operator_chat": "\n".join(lines),
            "steps": steps,
            "host": host,
            "port": port,
            "app_database": app_db,
            "app_username": app_user,
            "pgvector_ok": pgvector_ok,
            "pgvector_detail": pgvector_detail,
            "applied_schema_version": applied_version,
            "expected_schema_version": SCHEMA_VERSION,
        }
    )


if __name__ == "__main__":
    main()
