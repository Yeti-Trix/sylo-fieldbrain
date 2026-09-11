#!/usr/bin/env python3
"""Postgres + pgvector + schema version check for fieldbrain_db_check tool."""

from __future__ import annotations

import argparse

from _db_lib import SCHEMA_VERSION, connection_summary, run_health_check
from _json_out import emit, emit_error
from services.pgvector_windows import layman_pgvector_steps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--guided",
        action="store_true",
        help="Include guided setup steps when checks fail",
    )
    args = parser.parse_args()

    summary = run_health_check()
    connected = summary.get("postgres_connected") is True
    schema_ok = summary.get("schema_ok") is True
    pgvector_ok = summary.get("pgvector_available") is True

    if not connected:
        payload = {
            "ok": False,
            "error": summary.get("postgres_error", "Could not connect to PostgreSQL"),
            **summary,
        }
        if args.guided:
            payload["guided_setup"] = _guided_postgres_steps()
        emit(payload)

    lines = [
        f"PostgreSQL: connected ({summary.get('database_url_host')}:{summary.get('database_url_port')}/{summary.get('database_url_name')})",
        f"Config: {summary.get('config_source')} ({summary.get('config_file')})",
        f"Schema: {summary.get('schema_message')}",
        f"pgvector: {'enabled' if pgvector_ok else 'missing — semantic search unavailable until installed'}",
        f"Ollama endpoint: {summary.get('ollama_url')}",
    ]

    if not schema_ok:
        applied = summary.get("applied_schema_version")
        expected = summary.get("expected_schema_version", SCHEMA_VERSION)
        needs_migration = (
            summary.get("postgres_connected") is True
            and isinstance(applied, int)
            and applied < expected
        ) or (
            summary.get("postgres_connected") is True and applied is None
        )
        payload = {
            "ok": False,
            "error": summary.get("schema_message"),
            "operator_chat": "\n".join(lines),
            "needs_migration": needs_migration,
            **summary,
        }
        if args.guided:
            payload["guided_setup"] = _guided_migrate_steps()
        emit(payload)

    payload: dict = {
        "ok": True,
        "operator_chat": "\n".join(lines),
        **summary,
        "expected_schema_version": SCHEMA_VERSION,
    }
    if not pgvector_ok:
        major = summary.get("postgres_major")
        payload["pgvector_setup"] = layman_pgvector_steps(
            major if isinstance(major, int) else None,
            files_installed=bool(summary.get("vector_files_installed")),
            db_mode="remote"
            if str(summary.get("database_url_host") or "") not in ("localhost", "127.0.0.1")
            else "local",
        )
    emit(payload)


def _guided_postgres_steps() -> list[str]:
    return [
        "Install PostgreSQL 13+ as a Windows service — download from https://www.postgresql.org/download/windows/",
        "Optional — semantic search: download pgvector for your Postgres major version from "
        "https://github.com/andreiramani/pgvector_pgsql_windows/releases and extract the zip.",
        "FieldBrain Settings → Create database & migrate (button; superuser password not saved).",
        "Optional: Browse to the pgvector folder or zip → Install pgvector & enable semantic search.",
        "Test connection. Shop laptops: set dbMode remote + server IP.",
    ]


def _guided_migrate_steps() -> list[str]:
    return [
        "Sylo auto-applies database updates on startup when FieldBrain is enabled (one machine is enough for a shared DB).",
        "Or FieldBrain Settings → Apply database updates (next to Test connection).",
        "Or chat: fieldbrain_db_migrate.",
        "After migrate succeeds, restart other Sylo installs (they pick up the new schema automatically).",
    ]


if __name__ == "__main__":
    main()
