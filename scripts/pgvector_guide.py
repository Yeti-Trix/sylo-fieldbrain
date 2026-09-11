#!/usr/bin/env python3
"""Layman pgvector setup guide for FieldBrain."""

from __future__ import annotations

from _db_lib import load_database_config, run_health_check
from _json_out import emit
from services.pgvector_windows import layman_pgvector_steps, windows_install_status


def main() -> None:
    summary = run_health_check()
    cfg = load_database_config() or {}
    host = str(cfg.get("host") or "localhost").strip()
    db_mode = "remote" if host not in ("localhost", "127.0.0.1") else "local"

    major = summary.get("postgres_major")
    if isinstance(major, str) and major.isdigit():
        major = int(major)
    install = windows_install_status(major if isinstance(major, int) else None)
    pg_ok = summary.get("pgvector_available") is True
    steps = layman_pgvector_steps(
        major if isinstance(major, int) else None,
        files_installed=bool(install.get("vector_files_installed")),
        db_mode=db_mode,
    )
    if pg_ok:
        steps = [
            "pgvector is already enabled — semantic search is available when Ollama is running.",
        ]
    emit(
        {
            "ok": True,
            "pgvector_ok": pg_ok,
            "operator_chat": "\n".join(steps),
            "pgvector_setup": steps,
            **summary,
            **install,
        }
    )


if __name__ == "__main__":
    main()
