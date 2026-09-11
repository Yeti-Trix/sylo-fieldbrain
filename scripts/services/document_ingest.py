"""Document ingestion: extract text, chunk, index, optional embed via Ollama."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from _db_lib import check_pgvector, ollama_base_url
from models import Document, GlobalSettings
from services.document_service import ALLOWED_EXTENSIONS, register_document_from_path, read_document_bytes
from services.embedding_service import generate_embeddings
from services.global_brain_support import get_global_brain_shell_project_id

logger = logging.getLogger(__name__)

SOURCE_DOCUMENT = "document"
CHUNK_TARGET_CHARS = 500


def extract_text_from_bytes(data: bytes, ext: str) -> str:
    """Extract plain text from PDF (pymupdf) or .txt bytes."""
    ext_l = ext.lower()
    if ext_l == ".pdf":
        import fitz

        doc = fitz.open(stream=data, filetype="pdf")
        try:
            parts = [page.get_text() for page in doc]
        finally:
            doc.close()
        return "\n".join(parts).strip()
    if ext_l == ".txt":
        return data.decode("utf-8", errors="replace").strip()
    raise ValueError(f"Unsupported file type {ext_l}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")


def extract_text_from_file(path: Path) -> str:
    """Extract plain text from PDF (pymupdf) or .txt on disk."""
    return extract_text_from_bytes(path.read_bytes(), path.suffix.lower())


def extract_text_from_document(document: Document) -> str:
    ext = Path(document.original_filename or document.stored_path).suffix.lower()
    if not ext and document.mime_type == "application/pdf":
        ext = ".pdf"
    data = read_document_bytes(document)
    return extract_text_from_bytes(data, ext)


def chunk_text_chars(text_body: str, target_chars: int = CHUNK_TARGET_CHARS) -> list[str]:
    """Split text into ~target_chars chunks on sentence boundaries."""
    if not text_body or not text_body.strip():
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text_body.strip())
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        sent_len = len(sent)
        if current and current_len + sent_len + 1 > target_chars:
            chunks.append(" ".join(current))
            current = [sent]
            current_len = sent_len
        else:
            current.append(sent)
            current_len += sent_len + (1 if current_len else 0)

    if current:
        chunks.append(" ".join(current))

    return chunks or [text_body.strip()]


def _insert_index_row(
    session: Session,
    project_id: int,
    *,
    source_id: str,
    label: str,
    content: str,
    chunk_index: int,
) -> int:
    row = session.execute(
        text(
            """
            INSERT INTO search_index
                (project_id, source_type, source_id, label, path, content, search_vector, chunk_index)
            VALUES
                (:pid, :stype, :sid, :label, :path, :content,
                 setweight(to_tsvector('english', coalesce(:label,'')), 'A') ||
                   setweight(to_tsvector('english', coalesce(:path,'')), 'B') ||
                   setweight(to_tsvector('english', coalesce(:content,'')), 'D'),
                 :ci)
            RETURNING id
            """
        ),
        {
            "pid": project_id,
            "stype": SOURCE_DOCUMENT,
            "sid": source_id[:500],
            "label": label[:500],
            "path": label[:500],
            "content": content or " ",
            "ci": chunk_index,
        },
    ).fetchone()
    return int(row[0])


def _remove_document_index_rows(session: Session, project_id: int, document_id: int) -> None:
    session.execute(
        text(
            """
            DELETE FROM search_index
            WHERE project_id = :pid AND source_type = :stype AND source_id = :sid
            """
        ),
        {"pid": project_id, "stype": SOURCE_DOCUMENT, "sid": str(document_id)},
    )


def _embed_index_rows(session: Session, row_ids: list[int]) -> int:
    if not row_ids:
        return 0

    pg_ok, _ = check_pgvector()
    if not pg_ok:
        return 0

    settings = session.query(GlobalSettings).filter(GlobalSettings.id == 1).first()
    model = (settings.embedding_model if settings else None) or "nomic-embed-text"
    endpoint = ollama_base_url()

    rows = session.execute(
        text("SELECT id, content FROM search_index WHERE id = ANY(:ids)"),
        {"ids": row_ids},
    ).fetchall()
    if not rows:
        return 0

    texts = [(r[1] or " ") for r in rows]
    embeddings = generate_embeddings(texts, endpoint=endpoint, model=model)
    updated = 0
    for (row_id, _), emb in zip(rows, embeddings):
        if not emb:
            continue
        emb_str = "[" + ",".join(str(v) for v in emb) + "]"
        session.execute(
            text("UPDATE search_index SET embedding = CAST(:emb AS vector) WHERE id = :id"),
            {"emb": emb_str, "id": row_id},
        )
        updated += 1
    return updated


def _index_project_id_for_document(session: Session, doc: Document, project_id: int | None) -> int:
    scope = (doc.scope or "project_local").strip().lower()
    if scope == "global":
        return get_global_brain_shell_project_id(session)
    if project_id is not None:
        return project_id
    if doc.owner_project_id is not None:
        return int(doc.owner_project_id)
    raise ValueError("project_id required for project-scoped document indexing")


def index_document_text(
    session: Session,
    document: Document,
    full_text: str,
    *,
    index_project_id: int,
) -> dict[str, Any]:
    """Chunk document text into search_index and optionally embed."""
    _remove_document_index_rows(session, index_project_id, document.id)
    label = document.title or document.original_filename or "Document"
    chunks = chunk_text_chars(full_text)
    row_ids: list[int] = []

    for ci, chunk in enumerate(chunks):
        header = f"[{label}]"
        body = f"{header}\n\n{chunk.strip()}"
        row_id = _insert_index_row(
            session,
            index_project_id,
            source_id=str(document.id),
            label=label,
            content=body,
            chunk_index=ci,
        )
        row_ids.append(row_id)

    embedded = _embed_index_rows(session, row_ids)
    session.commit()
    return {
        "chunks_indexed": len(row_ids),
        "embeddings_written": embedded,
        "index_project_id": index_project_id,
    }


def ingest_document_file(
    session: Session,
    file_path: str | Path,
    *,
    scope: str,
    project_id: int | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Register (if needed), extract text, index, and optionally embed a document."""
    path = Path(file_path).expanduser().resolve()
    reg = register_document_from_path(
        session,
        path,
        scope=scope,
        project_id=project_id,
        title=title,
        attach=True,
    )
    document = (
        session.query(Document)
        .filter(Document.id == reg["document"]["id"])
        .first()
    )
    if not document:
        raise ValueError("Document registration failed")

    full_text = extract_text_from_document(document)
    index_pid = _index_project_id_for_document(session, document, project_id)
    index_stats = index_document_text(
        session,
        document,
        full_text,
        index_project_id=index_pid,
    )

    return {
        "document_id": document.id,
        "title": document.title,
        "scope": document.scope,
        "stored_path": document.stored_path,
        "text_chars": len(full_text),
        **index_stats,
    }
