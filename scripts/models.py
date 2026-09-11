"""SQLAlchemy models for sylo-logicscout shared Postgres data.

Auth, chat, and batch L5X analysis job tables are intentionally omitted.
Sylo SQLite owns chats; LogicForge owns L5X parse tooling.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import declarative_base

Base = declarative_base()

DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434"


class Project(Base):
    """Project metadata (L5X path/hash point at LogicForge-managed files)."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    controller_name = Column(String(255), nullable=True)
    processor_type = Column(String(100), nullable=True)
    software_revision = Column(String(50), nullable=True)
    l5x_file_path = Column(String(500), nullable=True)
    l5x_file_hash = Column(String(64), nullable=True, index=True)
    plc_ip = Column(String(45), nullable=True)
    plc_read_enabled = Column(Boolean, default=False, nullable=False)
    max_alert_chats = Column(Integer, nullable=False, default=10)
    hmi_embed_token = Column(String(255), nullable=True)
    cross_project_share = Column(String(20), nullable=False, default="share")
    cross_project_search = Column(Boolean, nullable=False, default=True)
    org_id = Column(String(100), nullable=False, default="default", index=True)
    project_tags_json = Column(Text, nullable=True)
    domain = Column(String(100), nullable=True)
    controller_family = Column(String(100), nullable=True)
    reminders_muted = Column(Boolean, nullable=False, default=False)
    is_system_hidden = Column(Boolean, nullable=False, default=False, server_default="false")
    job_number = Column(String(20), nullable=True, index=True)
    parent_project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    l5x_status = Column(String(20), nullable=False, default="analyzed")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Document(Base):
    """Uploaded document metadata; ingestion pipeline fills analysis rows later."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    scope = Column(String(20), nullable=False, default="project_local", index=True)
    owner_project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    category = Column(String(20), nullable=False, default="other", index=True)
    tags_json = Column(Text, nullable=True)
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    version = Column(String(50), nullable=True)
    archived = Column(Boolean, nullable=False, default=False)
    file_content = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (UniqueConstraint("file_hash", name="uq_documents_file_hash"),)


class ProjectDocumentLink(Base):
    """Attach a document to a project."""

    __tablename__ = "project_document_links"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="reference", index=True)
    attached_at = Column(DateTime, default=func.now())

    __table_args__ = (UniqueConstraint("project_id", "document_id", name="uq_project_document_link"),)


class GlobalSettings(Base):
    """Server-wide settings singleton."""

    __tablename__ = "global_settings"

    id = Column(Integer, primary_key=True, index=True)
    ollama_endpoint = Column(String(500), nullable=True, default=DEFAULT_OLLAMA_ENDPOINT)
    llm_model = Column(String(100), nullable=True)
    summarizer_model = Column(String(100), nullable=True)
    vision_model = Column(String(100), nullable=True)
    doc_vision_model = Column(String(100), nullable=True)
    analysis_model = Column(String(100), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    search_index_schema_version = Column(Integer, nullable=False, default=1, server_default="1")
    search_query_expansion = Column(Boolean, nullable=False, default=True)
    search_reranking_enabled = Column(Boolean, nullable=False, default=True)
    search_rerank_pool = Column(Integer, nullable=False, default=15)
    search_context_window = Column(Integer, nullable=False, default=1)
    search_rerank_backend = Column(String(20), nullable=False, default="ollama")
    search_rerank_model = Column(String(100), nullable=True)
    ollama_num_ctx = Column(Integer, nullable=True)
    ollama_num_ctx_agents_json = Column(Text, nullable=True)
    ollama_profiles_json = Column(Text, nullable=True)
    ollama_agent_endpoints_json = Column(Text, nullable=True)
    marker_pdf_enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    marker_pdf_use_llm = Column(Boolean, nullable=False, default=False, server_default="false")
    marker_pdf_ollama_model = Column(String(100), nullable=True)
    vision_render_dpi = Column(Integer, nullable=False, default=200, server_default="200")
    max_inflight_vision = Column(Integer, nullable=False, default=1, server_default="1")
    max_inflight_text = Column(Integer, nullable=False, default=1, server_default="1")
    l5x_analysis_concurrency = Column(Integer, nullable=False, default=1, server_default="1")
    vision_timeout_seconds = Column(Integer, nullable=False, default=300, server_default="300")
    text_timeout_seconds = Column(Integer, nullable=False, default=180, server_default="180")
    find_logic_llm_model = Column(String(100), nullable=True)
    documentation_search_llm_model = Column(String(100), nullable=True)
    orchestrator_temperature = Column(Float, nullable=True)
    summarizer_temperature = Column(Float, nullable=True)
    summarizer_max_summary_chars = Column(Integer, nullable=True)
    vision_temperature = Column(Float, nullable=True)
    doc_vision_temperature = Column(Float, nullable=True)
    analysis_temperature = Column(Float, nullable=True)
    documentation_search_temperature = Column(Float, nullable=True)
    find_logic_temperature = Column(Float, nullable=True)
    search_rerank_temperature = Column(Float, nullable=True)
    orchestrator_max_iterations = Column(Integer, nullable=True)
    find_logic_default_max_iterations = Column(Integer, nullable=True)
    documentation_search_default_max_iterations = Column(Integer, nullable=True)
    find_logic_effort_low_max_iterations = Column(Integer, nullable=True)
    find_logic_effort_medium_max_iterations = Column(Integer, nullable=True)
    find_logic_effort_high_max_iterations = Column(Integer, nullable=True)
    find_logic_system_prompt_extra = Column(Text, nullable=True)
    find_logic_inner_user_message = Column(Text, nullable=True)
    find_logic_allowed_tools_json = Column(Text, nullable=True)
    ollama_warmup_on_start = Column(Boolean, nullable=False, default=False, server_default=sql_text("false"))
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class DocumentAnalysis(Base):
    """LLM-generated analysis for an uploaded document."""

    __tablename__ = "document_analyses"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    llm_index_description = Column(Text, nullable=False)
    parsed_text_with_images = Column(Text, nullable=True)
    analyzed_at = Column(DateTime, default=func.now())


class DocumentPageImage(Base):
    """Vision-model description for a document page containing images or diagrams."""

    __tablename__ = "document_page_images"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    has_images = Column(Boolean, default=True, nullable=False)
    llm_image_description = Column(Text, nullable=True)
    llm_page_detail = Column(Text, nullable=True)
    ocr_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


class DocumentPdfOutline(Base):
    """Per-document TOC entries (physical_pdf_page is 0-based)."""

    __tablename__ = "document_pdf_outline"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(Integer, nullable=False)
    title = Column(Text, nullable=False)
    toc_page_claimed = Column(Integer, nullable=True)
    physical_pdf_page = Column(Integer, nullable=False)
    verification = Column(String(32), nullable=False)
    sequence = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())


class Alert(Base):
    """Tag-monitoring alert definition."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_name = Column(String(255), nullable=False)
    trigger_value_type = Column(String(20), nullable=False)
    trigger_operator = Column(String(20), nullable=False, default="eq")
    trigger_value = Column(Text, nullable=False)
    command = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AlertResponse(Base):
    """Agent response to a triggered alert."""

    __tablename__ = "alert_responses"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_value = Column(Text, nullable=True)
    agent_response = Column(Text, nullable=False, default="")
    is_processing = Column(Boolean, default=False, nullable=False)
    triggered_at = Column(DateTime, default=func.now())
    responded_at = Column(DateTime, nullable=True)


class TagTroubleshootingSolution(Base):
    """Human-approved resolution for a project tag."""

    __tablename__ = "tag_troubleshooting_solutions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_name = Column(String(255), nullable=False, index=True)
    solution_text = Column(Text, nullable=False)
    source_ref = Column(String(255), nullable=True)
    logged_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_tag_trouble_solutions_project_tag", "project_id", "tag_name"),)


class BrainDraft(Base):
    """Brain change audit record."""

    __tablename__ = "brain_drafts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_ref = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    op = Column(String(50), nullable=False)
    target_path = Column(String(500), nullable=False)
    payload_json = Column(Text, nullable=False)
    content_hash_before = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True)
    applied_at = Column(DateTime, nullable=True)


class MaintenanceLogEntry(Base):
    """Shop maintenance log entry (retrieval-first)."""

    __tablename__ = "maintenance_log_entries"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    fault_code = Column(String(100), nullable=True, index=True)
    equipment_tag = Column(String(255), nullable=True, index=True)
    logged_by = Column(String(100), nullable=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    search_vector = Column(TSVECTOR, nullable=True)


class MaintenanceLogRevision(Base):
    """Prior version of a maintenance log entry."""

    __tablename__ = "maintenance_log_revisions"

    id = Column(Integer, primary_key=True, index=True)
    log_entry_id = Column(
        Integer, ForeignKey("maintenance_log_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    fault_code = Column(String(100), nullable=True)
    equipment_tag = Column(String(255), nullable=True)
    logged_by = Column(String(100), nullable=True)
    revision_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())


class BrainDocument(Base):
    """Brain markdown stored in Postgres (canonical; local disk is optional cache)."""

    __tablename__ = "brain_documents"

    id = Column(Integer, primary_key=True, index=True)
    scope = Column(String(20), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    relative_path = Column(String(500), nullable=False)
    content = Column(Text, nullable=False, default="")
    deleted_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class BrainDocumentRevision(Base):
    """Prior version of a brain document."""

    __tablename__ = "brain_document_revisions"

    id = Column(Integer, primary_key=True, index=True)
    brain_document_id = Column(
        Integer, ForeignKey("brain_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relative_path = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    revision_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())


class SearchIndex(Base):
    """Hybrid search projection (tsvector + optional pgvector embedding).

    The ``embedding`` column is ``vector(768)`` when pgvector is installed;
    created in migration 002, not mapped here.
    """

    __tablename__ = "search_index"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    source_id = Column(String(500), nullable=True)
    label = Column(String(500), nullable=True)
    path = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    chunk_index = Column(Integer, default=0)
    section_id = Column(Integer, nullable=False, default=0)
    entry_share = Column(String(20), nullable=False, default="project_only")
    brain_type = Column(String(50), nullable=True)
    brain_status = Column(String(50), nullable=True)
