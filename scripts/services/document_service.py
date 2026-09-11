"""Document metadata queries and attach/register helpers for sylo-logicscout."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from models import Document, Project, ProjectDocumentLink
from services.brain_paths import storage_root
from services.document_formats import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    mime_for_ext,
    normalize_category,
)


def _file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def document_to_dict(document: Document, *, link_role: str | None = None) -> dict[str, Any]:
    return {
        "id": document.id,
        "scope": document.scope,
        "owner_project_id": document.owner_project_id,
        "title": document.title,
        "original_filename": document.original_filename,
        "stored_path": document.stored_path,
        "file_hash": document.file_hash,
        "mime_type": document.mime_type,
        "file_size": document.file_size,
        "category": document.category,
        "manufacturer": document.manufacturer,
        "model": document.model,
        "version": document.version,
        "archived": bool(document.archived),
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "tags": document.tags_json,
        "link_role": link_role,
    }


def get_document(session: Session, document_id: int) -> dict[str, Any] | None:
    document = (
        session.query(Document)
        .filter(Document.id == document_id, Document.archived.is_(False))
        .first()
    )
    if not document:
        return None
    return document_to_dict(document)


def list_documents_for_project(session: Session, project_id: int) -> list[dict[str, Any]]:
    rows = (
        session.query(Document, ProjectDocumentLink)
        .join(ProjectDocumentLink, ProjectDocumentLink.document_id == Document.id)
        .filter(ProjectDocumentLink.project_id == project_id, Document.archived.is_(False))
        .order_by(ProjectDocumentLink.attached_at.desc())
        .all()
    )
    return [document_to_dict(doc, link_role=link.role) for doc, link in rows]


def list_global_documents(
    session: Session,
    *,
    category: str | None = None,
    search: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    query = session.query(Document).filter(Document.scope == "global", Document.archived.is_(False))
    if category and category.strip():
        query = query.filter(Document.category == category.strip().lower())
    term = (search or "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(or_(Document.title.ilike(like), Document.original_filename.ilike(like)))
    cap = max(1, min(int(limit), 500))
    docs = query.order_by(Document.created_at.desc()).limit(cap).all()
    return [document_to_dict(d) for d in docs]


def promote_document_to_global(session: Session, document_id: int) -> dict[str, Any]:
    """Promote a project-local document to the global library.

    Re-scopes the row and moves its search_index rows to the global shell project
    (embeddings preserved, no re-index). The project link stays so the doc remains
    visible under its original project.
    """
    from services.global_brain_support import get_global_brain_shell_project_id

    doc = (
        session.query(Document)
        .filter(Document.id == document_id, Document.archived.is_(False))
        .first()
    )
    if not doc:
        raise ValueError("Document not found")
    if doc.scope == "global":
        return {"document": document_to_dict(doc), "promoted": False, "reason": "already_global"}
    if doc.scope != "project_local":
        raise ValueError(f"Cannot promote document with scope {doc.scope!r}")

    old_project_id = doc.owner_project_id
    global_pid = get_global_brain_shell_project_id(session)

    moved = 0
    if old_project_id is not None:
        result = session.execute(
            text(
                """
                UPDATE search_index
                SET project_id = :gpid
                WHERE project_id = :old_pid
                  AND source_type = 'document'
                  AND source_id = :sid
                """
            ),
            {"gpid": global_pid, "old_pid": old_project_id, "sid": str(doc.id)},
        )
        moved = result.rowcount or 0

    doc.scope = "global"
    session.commit()
    session.refresh(doc)

    return {
        "document": document_to_dict(doc),
        "promoted": True,
        "previous_project_id": old_project_id,
        "index_rows_moved": moved,
    }


def documents_storage_dir() -> Path:
    """Optional local cache directory (canonical bytes live in Postgres file_content)."""
    root = storage_root() / "documents"
    root.mkdir(parents=True, exist_ok=True)
    return root


def pg_stored_path(file_hash: str, ext: str) -> str:
    return f"pg://documents/{file_hash}{ext}"


def read_document_bytes(document: Document) -> bytes:
    if document.file_content:
        return bytes(document.file_content)
    path = Path(document.stored_path)
    if path.is_file():
        return path.read_bytes()
    raise ValueError(f"Document {document.id} has no file_content and stored_path is missing on disk")


def attach_document_to_project(
    session: Session,
    project_id: int,
    document_id: int,
    *,
    role: str = "reference",
) -> dict[str, Any]:
    """Attach an existing library or project-local document to a project."""
    proj = session.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise ValueError("Project not found")

    doc = (
        session.query(Document)
        .filter(Document.id == document_id, Document.archived.is_(False))
        .first()
    )
    if not doc:
        raise ValueError("Document not found")

    if doc.scope == "global":
        pass
    elif doc.scope == "project_local":
        if doc.owner_project_id != project_id:
            raise ValueError(
                "Document belongs to another project. Promote to global library first or attach from that project."
            )
    else:
        raise ValueError("Invalid document scope")

    role_norm = "schematic" if (role or "").lower() == "schematic" else "reference"
    link = (
        session.query(ProjectDocumentLink)
        .filter(
            ProjectDocumentLink.project_id == project_id,
            ProjectDocumentLink.document_id == document_id,
        )
        .first()
    )
    if link:
        if link.role != role_norm:
            link.role = role_norm
            session.commit()
            session.refresh(link)
        return {
            "document": document_to_dict(doc, link_role=link.role),
            "link": {"project_id": project_id, "document_id": document_id, "role": link.role},
            "already_linked": True,
        }

    link = ProjectDocumentLink(
        project_id=project_id,
        document_id=document_id,
        role=role_norm,
    )
    session.add(link)
    session.commit()
    session.refresh(link)
    return {
        "document": document_to_dict(doc, link_role=link.role),
        "link": {"project_id": project_id, "document_id": document_id, "role": link.role},
        "already_linked": False,
    }


def register_document_from_path(
    session: Session,
    source_path: Path,
    *,
    scope: str,
    project_id: int | None = None,
    title: str | None = None,
    category: str = "other",
    attach: bool = True,
) -> dict[str, Any]:
    """Copy a file into shared/storage/documents/ and create Document (+ optional link)."""
    if not source_path.is_file():
        raise ValueError(f"File not found: {source_path}")

    scope_norm = (scope or "project").strip().lower()
    if scope_norm == "global":
        doc_scope = "global"
        owner_project_id = None
        attach_project_id = project_id
    elif scope_norm == "project":
        if project_id is None:
            raise ValueError("project_id is required when scope is project")
        doc_scope = "project_local"
        owner_project_id = project_id
        attach_project_id = project_id
        proj = session.query(Project).filter(Project.id == project_id).first()
        if not proj:
            raise ValueError("Project not found")
    else:
        raise ValueError("scope must be global or project")

    ext = source_path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    size = source_path.stat().st_size
    if size > MAX_FILE_SIZE:
        raise ValueError(f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB limit")

    file_hash = _file_hash(source_path)
    existing = session.query(Document).filter(Document.file_hash == file_hash, Document.archived.is_(False)).first()
    file_bytes = source_path.read_bytes()

    if existing:
        doc = existing
        created = False
        if not doc.file_content:
            doc.file_content = file_bytes
            session.commit()
            session.refresh(doc)
    else:
        dest_name = f"{file_hash}{ext}"
        logical_path = pg_stored_path(file_hash, ext)
        # Optional local cache for operator inspection (not canonical).
        cache_path = documents_storage_dir() / dest_name
        if not cache_path.exists():
            cache_path.write_bytes(file_bytes)

        ttl = (title or "").strip() or source_path.stem
        doc = Document(
            scope=doc_scope,
            owner_project_id=owner_project_id,
            title=ttl[:255],
            original_filename=source_path.name[:255],
            stored_path=logical_path,
            file_hash=file_hash,
            mime_type=mime_for_ext(ext),
            file_size=size,
            category=normalize_category(category),
            file_content=file_bytes,
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)
        created = True

    linked = False
    if attach and attach_project_id is not None:
        result = attach_document_to_project(session, attach_project_id, doc.id)
        linked = not result.get("already_linked", False)

    return {
        "document": document_to_dict(doc),
        "created": created,
        "linked": linked,
        "scope": doc.scope,
    }
