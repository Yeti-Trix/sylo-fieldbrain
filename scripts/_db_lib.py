#!/usr/bin/env python3
"""Postgres access for sylo-fieldbrain — single funnel for all tools."""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Bump when Alembic head revision changes (must match latest migration).
SCHEMA_VERSION = 6

DEFAULT_DATABASE_URL = "postgresql://fieldbrain:fieldbrain@localhost:5432/fieldbrain"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"

_engine_singleton: Engine | None = None


def package_root() -> Path:
    return Path(__file__).resolve().parent.parent


def config_dir() -> Path:
    override = os.environ.get("SYLO_FIELDBRAIN_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    legacy = os.environ.get("SYLO_LOGICSCOUT_CONFIG_DIR", "").strip()
    if legacy:
        return Path(legacy).expanduser()
    return Path.home() / ".sylo" / "fieldbrain"


def config_path() -> Path:
    return config_dir() / "database_config.json"


def load_database_config() -> dict[str, Any] | None:
    path = config_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
    return None


def save_database_config(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str = "",
) -> Path:
    """Persist connection fields. Empty password keeps existing when file already exists."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_database_config() or {}
    pwd = password if password else str(existing.get("password") or "")
    payload = {
        "host": host.strip(),
        "port": int(port),
        "database": database.strip(),
        "username": username.strip(),
        "password": pwd,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def build_database_url() -> str:
    env_url = os.environ.get("SYLO_FIELDBRAIN_DATABASE_URL", "").strip()
    if not env_url:
        env_url = os.environ.get("SYLO_LOGICSCOUT_DATABASE_URL", "").strip()
    if env_url:
        return env_url

    config = load_database_config()
    if config:
        host = str(config.get("host") or "localhost")
        port = int(config.get("port") or 5432)
        database = str(config.get("database") or "fieldbrain")
        username = str(config.get("username") or "fieldbrain")
        password = str(config.get("password") or "")
        safe_password = urllib.parse.quote_plus(password) if password else ""
        auth = f"{username}:{safe_password}@" if safe_password else f"{username}@"
        return f"postgresql://{auth}{host}:{port}/{database}"

    legacy = os.environ.get("DATABASE_URL", "").strip()
    if legacy.startswith("postgresql"):
        return legacy

    return DEFAULT_DATABASE_URL


def ollama_base_url() -> str:
    url = os.environ.get("SYLO_FIELDBRAIN_OLLAMA_URL", "").strip()
    if not url:
        url = os.environ.get("SYLO_LOGICSCOUT_OLLAMA_URL", "").strip()
    return url or DEFAULT_OLLAMA_URL


def reset_engine() -> None:
    global _engine_singleton
    if _engine_singleton is not None:
        try:
            _engine_singleton.dispose()
        except Exception as exc:
            logger.warning("Engine dispose failed: %s", exc)
    _engine_singleton = None


def get_engine(*, echo: bool = False) -> Engine:
    global _engine_singleton
    if _engine_singleton is not None:
        return _engine_singleton

    url = build_database_url()
    if not url.startswith("postgresql"):
        raise RuntimeError(
            f"FieldBrain requires PostgreSQL. Got {url!r}. "
            "Set SYLO_FIELDBRAIN_DATABASE_URL or ~/.sylo/fieldbrain/database_config.json"
        )
    _engine_singleton = create_engine(url, pool_pre_ping=True, echo=echo)
    return _engine_singleton


def read_applied_schema_version(engine: Engine | None = None) -> int | None:
    eng = engine or get_engine()
    with eng.connect() as conn:
        row = conn.execute(
            text("SELECT version FROM logicscout_schema_meta ORDER BY id DESC LIMIT 1")
        ).fetchone()
        if row is None:
            return None
        return int(row[0])


def verify_schema_version(engine: Engine | None = None) -> tuple[bool, str]:
    """Return (ok, message). Fail loud on mismatch or missing meta table."""
    eng = engine or get_engine()
    try:
        applied = read_applied_schema_version(eng)
    except Exception as exc:
        return False, f"Schema meta unreadable (run fieldbrain_db_migrate): {exc}"

    if applied is None:
        return False, "Database not initialized — run fieldbrain_db_migrate before using FieldBrain tools."

    if applied != SCHEMA_VERSION:
        return (
            False,
            f"Schema version mismatch: database has {applied}, package expects {SCHEMA_VERSION}. "
            "Run fieldbrain_db_migrate on one Sylo install, then restart others.",
        )
    return True, f"Schema version {applied} OK"


def check_pgvector(engine: Engine | None = None) -> tuple[bool, str | None]:
    eng = engine or get_engine()
    with eng.connect() as conn:
        try:
            row = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
            if row:
                return True, str(row[0])
        except Exception as exc:
            return False, str(exc)
    return False, None


def connection_summary() -> dict[str, Any]:
    url = build_database_url()
    parsed = urllib.parse.urlparse(url)
    config = load_database_config()
    return {
        "database_url_host": parsed.hostname or "localhost",
        "database_url_port": parsed.port or 5432,
        "database_url_name": (parsed.path or "/fieldbrain").lstrip("/"),
        "database_url_user": parsed.username or "fieldbrain",
        "config_file": str(config_path()),
        "config_file_exists": config_path().is_file(),
        "config_source": "env" if os.environ.get("SYLO_FIELDBRAIN_DATABASE_URL") or os.environ.get("SYLO_LOGICSCOUT_DATABASE_URL") else (
            "file" if config else "default"
        ),
        "ollama_url": ollama_base_url(),
        "expected_schema_version": SCHEMA_VERSION,
    }


def run_health_check() -> dict[str, Any]:
    summary = connection_summary()
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        summary["postgres_connected"] = True
    except Exception as exc:
        summary["postgres_connected"] = False
        summary["postgres_error"] = str(exc)
        return summary

    from services.pgvector_windows import detect_postgres_major, windows_install_status

    summary["postgres_major"] = detect_postgres_major(engine)
    install = windows_install_status(summary["postgres_major"])
    summary.update(install)

    pg_ok, pg_detail = check_pgvector(engine)
    summary["pgvector_available"] = pg_ok
    summary["pgvector_detail"] = pg_detail

    schema_ok, schema_msg = verify_schema_version(engine)
    summary["schema_ok"] = schema_ok
    summary["schema_message"] = schema_msg
    summary["applied_schema_version"] = read_applied_schema_version(engine)
    return summary
