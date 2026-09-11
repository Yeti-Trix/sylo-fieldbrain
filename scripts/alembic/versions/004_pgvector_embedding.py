"""Add search_index.embedding when pgvector is available (schema version 4).

Revision ID: 004_pgvector_embedding
Revises: 003_durability
Create Date: 2026-07-04
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "004_pgvector_embedding"
down_revision = "003_durability"
branch_labels = None
depends_on = None


def _pgvector_available(connection) -> bool:
    row = connection.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    ).fetchone()
    return row is not None


def upgrade() -> None:
    connection = op.get_bind()
    if _pgvector_available(connection):
        op.execute("ALTER TABLE search_index ADD COLUMN IF NOT EXISTS embedding vector(768)")
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_search_index_embedding
            ON search_index USING hnsw (embedding vector_cosine_ops)
            """
        )
    op.execute("INSERT INTO logicscout_schema_meta (version) VALUES (4)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_search_index_embedding")
    op.execute("ALTER TABLE search_index DROP COLUMN IF EXISTS embedding")
    op.execute("DELETE FROM logicscout_schema_meta WHERE version = 4")
