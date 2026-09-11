"""Add projects.job_number for grouping sub-jobs (schema version 5).

Revision ID: 005_project_job_number
Revises: 004_pgvector_embedding
Create Date: 2026-07-04
"""

from __future__ import annotations

from alembic import op

revision = "005_project_job_number"
down_revision = "004_pgvector_embedding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS job_number VARCHAR(20)")
    op.execute(
        """
        UPDATE projects
        SET job_number = split_part(name, '-', 1)
        WHERE job_number IS NULL
          AND name ~ '^[0-9]{5}-[0-9]{3}$'
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_projects_job_number ON projects (job_number)"
    )
    op.execute("INSERT INTO logicscout_schema_meta (version) VALUES (5)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_projects_job_number")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS job_number")
    op.execute("DELETE FROM logicscout_schema_meta WHERE version = 5")
