"""Add projects.parent_project_id for job vs sub-project hierarchy (schema version 6).

Revision ID: 006_project_parent
Revises: 005_project_job_number
Create Date: 2026-07-04
"""

from __future__ import annotations

from alembic import op

revision = "006_project_parent"
down_revision = "005_project_job_number"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS parent_project_id INTEGER
        REFERENCES projects(id) ON DELETE SET NULL
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_projects_parent_project_id ON projects (parent_project_id)"
    )
    op.execute(
        """
        UPDATE projects sub
        SET parent_project_id = parent.id
        FROM projects parent
        WHERE sub.name ~ '^[0-9]{5}-[0-9]{3}$'
          AND parent.name = split_part(sub.name, '-', 1)
          AND parent.name ~ '^[0-9]{5}$'
          AND sub.parent_project_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE projects
        SET job_number = split_part(name, '-', 1)
        WHERE job_number IS NULL
          AND name ~ '^[0-9]{5}-[0-9]{3}$'
        """
    )
    op.execute(
        """
        UPDATE projects
        SET job_number = name
        WHERE job_number IS NULL
          AND name ~ '^[0-9]{5}$'
        """
    )
    op.execute("INSERT INTO logicscout_schema_meta (version) VALUES (6)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_projects_parent_project_id")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS parent_project_id")
    op.execute("DELETE FROM logicscout_schema_meta WHERE version = 6")
