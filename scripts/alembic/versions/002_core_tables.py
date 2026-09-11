"""Core LogicScout shared tables (schema version 2).

Revision ID: 002_core_tables
Revises: 001_baseline
Create Date: 2026-07-04
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "002_core_tables"
down_revision = "001_baseline"
branch_labels = None
depends_on = None


def _pgvector_available(connection) -> bool:
    row = connection.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    ).fetchone()
    return row is not None


def _try_create_pgvector(connection) -> bool:
    if _pgvector_available(connection):
        return True
    try:
        autocommit = connection.execution_options(isolation_level="AUTOCOMMIT")
        autocommit.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:
        return False
    return _pgvector_available(connection)


def _add_column_if_not_exists(table: str, column: str, coltype: str) -> None:
    op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}")


def _ensure_project_columns() -> None:
    columns = [
        ("max_alert_chats", "INTEGER NOT NULL DEFAULT 10"),
        ("hmi_embed_token", "VARCHAR(255)"),
        ("cross_project_share", "VARCHAR(20) NOT NULL DEFAULT 'share'"),
        ("cross_project_search", "BOOLEAN NOT NULL DEFAULT TRUE"),
        ("org_id", "VARCHAR(100) NOT NULL DEFAULT 'default'"),
        ("project_tags_json", "TEXT"),
        ("domain", "VARCHAR(100)"),
        ("controller_family", "VARCHAR(100)"),
        ("reminders_muted", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("is_system_hidden", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("l5x_status", "VARCHAR(20) NOT NULL DEFAULT 'analyzed'"),
    ]
    for name, typedef in columns:
        _add_column_if_not_exists("projects", name, typedef)


def upgrade() -> None:
    connection = op.get_bind()
    has_pgvector = _try_create_pgvector(connection)

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            controller_name VARCHAR(255),
            processor_type VARCHAR(100),
            software_revision VARCHAR(50),
            l5x_file_path VARCHAR(500),
            l5x_file_hash VARCHAR(64),
            plc_ip VARCHAR(45),
            plc_read_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            max_alert_chats INTEGER NOT NULL DEFAULT 10,
            hmi_embed_token VARCHAR(255),
            cross_project_share VARCHAR(20) NOT NULL DEFAULT 'share',
            cross_project_search BOOLEAN NOT NULL DEFAULT TRUE,
            org_id VARCHAR(100) NOT NULL DEFAULT 'default',
            project_tags_json TEXT,
            domain VARCHAR(100),
            controller_family VARCHAR(100),
            reminders_muted BOOLEAN NOT NULL DEFAULT FALSE,
            is_system_hidden BOOLEAN NOT NULL DEFAULT FALSE,
            l5x_status VARCHAR(20) NOT NULL DEFAULT 'analyzed',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    _ensure_project_columns()
    op.execute("CREATE INDEX IF NOT EXISTS ix_projects_name ON projects (name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_projects_l5x_file_hash ON projects (l5x_file_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_projects_org_id ON projects (org_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            scope VARCHAR(20) NOT NULL DEFAULT 'project_local',
            owner_project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            stored_path VARCHAR(500) NOT NULL,
            file_hash VARCHAR(64) NOT NULL,
            mime_type VARCHAR(100),
            file_size INTEGER,
            category VARCHAR(20) NOT NULL DEFAULT 'other',
            tags_json TEXT,
            manufacturer VARCHAR(100),
            model VARCHAR(100),
            version VARCHAR(50),
            archived BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_documents_file_hash UNIQUE (file_hash)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_scope ON documents (scope)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_owner_project_id ON documents (owner_project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_file_hash ON documents (file_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_category ON documents (category)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS project_document_links (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL DEFAULT 'reference',
            attached_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_project_document_link UNIQUE (project_id, document_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_document_links_project_id ON project_document_links (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_document_links_document_id ON project_document_links (document_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_document_links_role ON project_document_links (role)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS global_settings (
            id SERIAL PRIMARY KEY,
            ollama_endpoint VARCHAR(500) DEFAULT 'http://localhost:11434',
            llm_model VARCHAR(100),
            summarizer_model VARCHAR(100),
            vision_model VARCHAR(100),
            doc_vision_model VARCHAR(100),
            analysis_model VARCHAR(100),
            embedding_model VARCHAR(100),
            search_index_schema_version INTEGER NOT NULL DEFAULT 1,
            search_query_expansion BOOLEAN NOT NULL DEFAULT TRUE,
            search_reranking_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            search_rerank_pool INTEGER NOT NULL DEFAULT 15,
            search_context_window INTEGER NOT NULL DEFAULT 1,
            search_rerank_backend VARCHAR(20) NOT NULL DEFAULT 'ollama',
            search_rerank_model VARCHAR(100),
            ollama_num_ctx INTEGER,
            ollama_num_ctx_agents_json TEXT,
            ollama_profiles_json TEXT,
            ollama_agent_endpoints_json TEXT,
            marker_pdf_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            marker_pdf_use_llm BOOLEAN NOT NULL DEFAULT FALSE,
            marker_pdf_ollama_model VARCHAR(100),
            vision_render_dpi INTEGER NOT NULL DEFAULT 200,
            max_inflight_vision INTEGER NOT NULL DEFAULT 1,
            max_inflight_text INTEGER NOT NULL DEFAULT 1,
            l5x_analysis_concurrency INTEGER NOT NULL DEFAULT 1,
            vision_timeout_seconds INTEGER NOT NULL DEFAULT 300,
            text_timeout_seconds INTEGER NOT NULL DEFAULT 180,
            find_logic_llm_model VARCHAR(100),
            documentation_search_llm_model VARCHAR(100),
            orchestrator_temperature DOUBLE PRECISION,
            summarizer_temperature DOUBLE PRECISION,
            summarizer_max_summary_chars INTEGER,
            vision_temperature DOUBLE PRECISION,
            doc_vision_temperature DOUBLE PRECISION,
            analysis_temperature DOUBLE PRECISION,
            documentation_search_temperature DOUBLE PRECISION,
            find_logic_temperature DOUBLE PRECISION,
            search_rerank_temperature DOUBLE PRECISION,
            orchestrator_max_iterations INTEGER,
            find_logic_default_max_iterations INTEGER,
            documentation_search_default_max_iterations INTEGER,
            find_logic_effort_low_max_iterations INTEGER,
            find_logic_effort_medium_max_iterations INTEGER,
            find_logic_effort_high_max_iterations INTEGER,
            find_logic_system_prompt_extra TEXT,
            find_logic_inner_user_message TEXT,
            find_logic_allowed_tools_json TEXT,
            ollama_warmup_on_start BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        INSERT INTO global_settings (id)
        SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM global_settings WHERE id = 1)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_analyses (
            id SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
            llm_index_description TEXT NOT NULL,
            parsed_text_with_images TEXT,
            analyzed_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_analyses_document_id ON document_analyses (document_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_page_images (
            id SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            page_number INTEGER NOT NULL,
            has_images BOOLEAN NOT NULL DEFAULT TRUE,
            llm_image_description TEXT,
            llm_page_detail TEXT,
            ocr_text TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_page_images_document_id ON document_page_images (document_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_pdf_outline (
            id SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            level INTEGER NOT NULL,
            title TEXT NOT NULL,
            toc_page_claimed INTEGER,
            physical_pdf_page INTEGER NOT NULL,
            verification VARCHAR(32) NOT NULL,
            sequence INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_pdf_outline_document_id ON document_pdf_outline (document_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            tag_name VARCHAR(255) NOT NULL,
            trigger_value_type VARCHAR(20) NOT NULL,
            trigger_operator VARCHAR(20) NOT NULL DEFAULT 'eq',
            trigger_value TEXT NOT NULL,
            command TEXT NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_alerts_project_id ON alerts (project_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_responses (
            id SERIAL PRIMARY KEY,
            alert_id INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
            tag_value TEXT,
            agent_response TEXT NOT NULL DEFAULT '',
            is_processing BOOLEAN NOT NULL DEFAULT FALSE,
            triggered_at TIMESTAMP DEFAULT NOW(),
            responded_at TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_responses_alert_id ON alert_responses (alert_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tag_troubleshooting_solutions (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            tag_name VARCHAR(255) NOT NULL,
            solution_text TEXT NOT NULL,
            source_ref VARCHAR(255),
            logged_by VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tag_trouble_solutions_project_tag "
        "ON tag_troubleshooting_solutions (project_id, tag_name)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tag_troubleshooting_solutions_tag_name "
        "ON tag_troubleshooting_solutions (tag_name)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS brain_drafts (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            source_ref VARCHAR(255),
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            op VARCHAR(50) NOT NULL,
            target_path VARCHAR(500) NOT NULL,
            payload_json TEXT NOT NULL,
            content_hash_before VARCHAR(64),
            created_at TIMESTAMP DEFAULT NOW(),
            expires_at TIMESTAMP,
            applied_at TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_brain_drafts_project_id ON brain_drafts (project_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenance_log_entries (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
            title VARCHAR(255) NOT NULL,
            body TEXT NOT NULL,
            fault_code VARCHAR(100),
            equipment_tag VARCHAR(255),
            logged_by VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            search_vector tsvector
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_maintenance_log_entries_project_id ON maintenance_log_entries (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_maintenance_log_entries_fault_code ON maintenance_log_entries (fault_code)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_maintenance_log_entries_equipment_tag ON maintenance_log_entries (equipment_tag)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_maintenance_log_entries_created_at ON maintenance_log_entries (created_at)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_maintenance_log_search_vector "
        "ON maintenance_log_entries USING GIN (search_vector)"
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION maintenance_log_entries_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.body, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.fault_code, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.equipment_tag, '')), 'A');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_maintenance_log_entries_search_vector ON maintenance_log_entries")
    op.execute(
        """
        CREATE TRIGGER trg_maintenance_log_entries_search_vector
        BEFORE INSERT OR UPDATE OF title, body, fault_code, equipment_tag
        ON maintenance_log_entries
        FOR EACH ROW EXECUTE FUNCTION maintenance_log_entries_search_vector_update()
        """
    )

    embedding_col = ", embedding vector(768)" if has_pgvector else ""
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS search_index (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            source_type VARCHAR(50) NOT NULL,
            source_id VARCHAR(500),
            label VARCHAR(500),
            path VARCHAR(500),
            content TEXT,
            search_vector tsvector,
            chunk_index INTEGER DEFAULT 0,
            section_id INTEGER NOT NULL DEFAULT 0,
            entry_share VARCHAR(20) NOT NULL DEFAULT 'project_only',
            brain_type VARCHAR(50),
            brain_status VARCHAR(50)
            {embedding_col}
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_search_index_vector ON search_index USING GIN (search_vector)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_search_index_project ON search_index (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_search_index_source_type ON search_index (source_type)")
    if has_pgvector:
        try:
            op.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_search_index_embedding
                ON search_index USING hnsw (embedding vector_cosine_ops)
                """
            )
        except Exception:
            pass

    op.execute("INSERT INTO logicscout_schema_meta (version) VALUES (2)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS search_index CASCADE")
    op.execute("DROP TRIGGER IF EXISTS trg_maintenance_log_entries_search_vector ON maintenance_log_entries")
    op.execute("DROP FUNCTION IF EXISTS maintenance_log_entries_search_vector_update()")
    op.execute("DROP TABLE IF EXISTS maintenance_log_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS brain_drafts CASCADE")
    op.execute("DROP TABLE IF EXISTS tag_troubleshooting_solutions CASCADE")
    op.execute("DROP TABLE IF EXISTS alert_responses CASCADE")
    op.execute("DROP TABLE IF EXISTS alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS document_pdf_outline CASCADE")
    op.execute("DROP TABLE IF EXISTS document_page_images CASCADE")
    op.execute("DROP TABLE IF EXISTS document_analyses CASCADE")
    op.execute("DROP TABLE IF EXISTS global_settings CASCADE")
    op.execute("DROP TABLE IF EXISTS project_document_links CASCADE")
    op.execute("DROP TABLE IF EXISTS documents CASCADE")
    op.execute("DROP TABLE IF EXISTS projects CASCADE")
    op.execute("DELETE FROM logicscout_schema_meta WHERE version = 2")
