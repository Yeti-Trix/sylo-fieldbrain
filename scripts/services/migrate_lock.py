"""Postgres advisory lock while applying Alembic migrations (shared DB, many Sylo installs)."""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Stable lock id for FieldBrain schema migrations.
MIGRATE_LOCK_KEY = 74201904


@contextmanager
def migration_advisory_lock(engine: Engine):
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": MIGRATE_LOCK_KEY})
        conn.commit()
    try:
        yield
    finally:
        with engine.connect() as conn:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": MIGRATE_LOCK_KEY})
            conn.commit()
