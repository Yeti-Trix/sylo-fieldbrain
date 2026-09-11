#!/usr/bin/env python3
"""Enable pgvector in the FieldBrain database and ensure embedding schema."""

from __future__ import annotations

import argparse
import os
import urllib.parse

from sqlalchemy import create_engine, text

from _db_lib import SCHEMA_VERSION, check_pgvector, load_database_config, run_health_check
from _json_out import emit, emit_error
from services.pgvector_windows import layman_pgvector_steps, windows_install_status


def _build_admin_url(host: str, port: int, database: str, user: str, password: str) -> str:
    return (
        f"postgresql://{urllib.parse.quote(user)}:{urllib.parse.quote(password)}"
        f"@{host}:{port}/{urllib.parse.quote(database)}"
    )


def _try_create_extension(app_url: str) -> tuple[bool, str | None]:
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
        return False, "CREATE EXTENSION ran but vector extension not visible"
    except Exception as exc:
        return False, str(exc)
    finally:
        engine.dispose()


def _ensure_embedding_schema(app_url: str) -> tuple[bool, str | None]:
    engine = create_engine(app_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            pg_ok = conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
            if not pg_ok:
                return False, "pgvector extension not enabled in this database"
            conn.execute(
                text("ALTER TABLE search_index ADD COLUMN IF NOT EXISTS embedding vector(768)")
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_search_index_embedding
                    ON search_index USING hnsw (embedding vector_cosine_ops)
                    """
                )
            )
        return True, None
    except Exception as exc:
        return False, str(exc)
    finally:
        engine.dispose()


def _run_migrate(app_url: str) -> tuple[int | None, str | None]:
    from alembic import command

    from _db_lib import read_applied_schema_version, reset_engine
    from db_migrate import alembic_config

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
    parser.add_argument("--host", default="")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--database", default="")
    args = parser.parse_args()

    admin_password = (args.admin_password or os.environ.get("SYLO_FIELDBRAIN_BOOTSTRAP_ADMIN_PASSWORD") or "").strip()
    if not admin_password:
        emit_error("Postgres superuser password is required (not saved).")

    cfg = load_database_config() or {}
    host = (args.host or str(cfg.get("host") or "localhost")).strip()
    db_mode = "remote" if host not in ("localhost", "127.0.0.1") else "local"
    port = args.port or int(cfg.get("port") or 5432)
    database = (args.database or str(cfg.get("database") or "fieldbrain")).strip()
    admin_user = (args.admin_user or "postgres").strip()

    health = run_health_check()
    if health.get("postgres_connected") is not True:
        emit_error(health.get("postgres_error", "Connect to Postgres first (Test connection)."))

    major = health.get("postgres_major")
    if isinstance(major, str) and major.isdigit():
        major = int(major)
    install = windows_install_status(major if isinstance(major, int) else None)

    admin_url = _build_admin_url(host, port, database, admin_user, admin_password)
    ext_ok, ext_detail = _try_create_extension(admin_url)
    if not ext_ok:
        guide = layman_pgvector_steps(
            major if isinstance(major, int) else None,
            files_installed=bool(install.get("vector_files_installed")),
            db_mode=db_mode,
        )
        emit_error(
            f"Could not enable pgvector: {ext_detail}",
            pgvector_setup=guide,
            **install,
        )

    app_user = str(cfg.get("username") or "fieldbrain")
    app_password = str(cfg.get("password") or "")
    app_url = _build_admin_url(host, port, database, app_user, app_password)
    schema_ok, schema_err = _ensure_embedding_schema(app_url)
    if not schema_ok:
        emit_error(f"pgvector enabled but schema update failed: {schema_err}", pgvector_detail=ext_detail)

    applied, migrate_err = _run_migrate(app_url)
    if migrate_err:
        emit_error(migrate_err, pgvector_detail=ext_detail)

    pg_ok, pg_ver = check_pgvector()
    lines = [
        f"Semantic search enabled (pgvector {ext_detail}).",
        f"Schema version {applied}.",
        "Superuser password was not saved.",
        "Re-ingest documents later if you want embeddings on existing files.",
    ]
    emit(
        {
            "ok": True,
            "operator_chat": "\n".join(lines),
            "pgvector_ok": pg_ok,
            "pgvector_detail": pg_ver,
            "applied_schema_version": applied,
            **install,
        }
    )


if __name__ == "__main__":
    main()
