"""Baseline schema meta + pgvector extension attempt.

Revision ID: 001_baseline
Revises:
Create Date: 2026-07-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS logicscout_schema_meta (
            id SERIAL PRIMARY KEY,
            version INTEGER NOT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        INSERT INTO logicscout_schema_meta (version)
        SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM logicscout_schema_meta)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS logicscout_schema_meta")
