"""Durability: content in Postgres, soft delete, revision history (schema version 3).

Revision ID: 003_durability
Revises: 002_core_tables
Create Date: 2026-07-04
"""

from __future__ import annotations

from alembic import op

revision = "003_durability"
down_revision = "002_core_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE maintenance_log_entries ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_maintenance_log_entries_deleted_at "
        "ON maintenance_log_entries (deleted_at)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenance_log_revisions (
            id SERIAL PRIMARY KEY,
            log_entry_id INTEGER NOT NULL REFERENCES maintenance_log_entries(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            body TEXT NOT NULL,
            fault_code VARCHAR(100),
            equipment_tag VARCHAR(255),
            logged_by VARCHAR(100),
            revision_number INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_maintenance_log_revisions_entry "
        "ON maintenance_log_revisions (log_entry_id, revision_number DESC)"
    )

    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_content BYTEA")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS brain_documents (
            id SERIAL PRIMARY KEY,
            scope VARCHAR(20) NOT NULL,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            relative_path VARCHAR(500) NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            deleted_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_brain_documents_scope_project "
        "ON brain_documents (scope, project_id)"
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_brain_documents_global_active
        ON brain_documents (relative_path)
        WHERE scope = 'global' AND deleted_at IS NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_brain_documents_project_active
        ON brain_documents (project_id, relative_path)
        WHERE scope = 'project' AND deleted_at IS NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS brain_document_revisions (
            id SERIAL PRIMARY KEY,
            brain_document_id INTEGER NOT NULL REFERENCES brain_documents(id) ON DELETE CASCADE,
            relative_path VARCHAR(500) NOT NULL,
            content TEXT NOT NULL,
            revision_number INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_brain_document_revisions_doc "
        "ON brain_document_revisions (brain_document_id, revision_number DESC)"
    )

    op.execute("INSERT INTO logicscout_schema_meta (version) VALUES (3)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS brain_document_revisions CASCADE")
    op.execute("DROP TABLE IF EXISTS brain_documents CASCADE")
    op.execute("DROP TABLE IF EXISTS maintenance_log_revisions CASCADE")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS file_content")
    op.execute("ALTER TABLE maintenance_log_entries DROP COLUMN IF EXISTS deleted_at")
    op.execute("DELETE FROM logicscout_schema_meta WHERE version = 3")
