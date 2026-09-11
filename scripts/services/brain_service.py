"""Read/write brain markdown in Postgres with revisions and soft delete."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import BrainDocument, BrainDocumentRevision
from services.brain_paths import safe_relative_brain_path
from services.global_brain_support import ensure_global_brain_shell_project


def _scope_norm(scope: str) -> str:
    s = (scope or "project").strip().lower()
    if s not in ("global", "project"):
        raise ValueError("scope must be global or project")
    return s


def _resolve_scope_project(session: Session, scope: str, project_id: int | None) -> tuple[str, int | None]:
    scope_n = _scope_norm(scope)
    if scope_n == "global":
        ensure_global_brain_shell_project(session)
        return scope_n, None
    if project_id is None:
        raise ValueError("project_id is required when scope is project")
    return scope_n, project_id


def _active_brain_query(session: Session, scope: str, project_id: int | None, relative_path: str):
    scope_n, pid = _resolve_scope_project(session, scope, project_id)
    q = session.query(BrainDocument).filter(
        BrainDocument.scope == scope_n,
        BrainDocument.relative_path == relative_path,
        BrainDocument.deleted_at.is_(None),
    )
    if scope_n == "global":
        q = q.filter(BrainDocument.project_id.is_(None))
    else:
        q = q.filter(BrainDocument.project_id == pid)
    return q


def _next_brain_revision(session: Session, doc_id: int) -> int:
    current = (
        session.query(func.max(BrainDocumentRevision.revision_number))
        .filter(BrainDocumentRevision.brain_document_id == doc_id)
        .scalar()
    )
    return int(current or 0) + 1


def _save_brain_revision(session: Session, doc: BrainDocument) -> None:
    rev = BrainDocumentRevision(
        brain_document_id=doc.id,
        relative_path=doc.relative_path,
        content=doc.content,
        revision_number=_next_brain_revision(session, doc.id),
    )
    session.add(rev)


def brain_doc_to_dict(doc: BrainDocument) -> dict[str, Any]:
    return {
        "id": doc.id,
        "scope": doc.scope,
        "project_id": doc.project_id,
        "relative_path": doc.relative_path,
        "content": doc.content,
        "size_bytes": len((doc.content or "").encode("utf-8")),
        "deleted_at": doc.deleted_at.isoformat() if doc.deleted_at else None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def brain_doc_list_item(doc: BrainDocument) -> dict[str, Any]:
    return {
        "id": doc.id,
        "scope": doc.scope,
        "project_id": doc.project_id,
        "relative_path": doc.relative_path,
        "size_bytes": len((doc.content or "").encode("utf-8")),
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def list_brain_documents(
    session: Session,
    *,
    scope: str = "project",
    project_id: int | None = None,
    search: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    scope_n = _scope_norm(scope)
    query = session.query(BrainDocument).filter(BrainDocument.deleted_at.is_(None))
    if scope_n == "global":
        query = query.filter(BrainDocument.scope == "global", BrainDocument.project_id.is_(None))
    else:
        if project_id is None:
            raise ValueError("project_id is required when scope is project")
        query = query.filter(BrainDocument.scope == "project", BrainDocument.project_id == project_id)

    term = (search or "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(BrainDocument.relative_path.ilike(like))

    cap = max(1, min(int(limit), 500))
    rows = query.order_by(BrainDocument.relative_path.asc()).limit(cap).all()
    return [brain_doc_list_item(d) for d in rows]


def read_brain_markdown(
    session: Session,
    *,
    scope: str,
    relative_path: str,
    project_id: int | None = None,
) -> dict[str, Any]:
    rel = safe_relative_brain_path(relative_path)
    if not rel:
        raise ValueError("Invalid brain path (must be a .md file under brain/, no .. segments)")

    doc = _active_brain_query(session, scope, project_id, rel).first()
    if not doc:
        raise ValueError(f"Brain file not found: {rel}")

    result = brain_doc_to_dict(doc)
    result["storage"] = "postgres"
    return result


def write_brain_markdown(
    session: Session,
    *,
    scope: str,
    relative_path: str,
    content: str,
    project_id: int | None = None,
    mode: str = "replace",
) -> dict[str, Any]:
    rel = safe_relative_brain_path(relative_path)
    if not rel:
        raise ValueError("Invalid brain path (must be a .md file under brain/, no .. segments)")

    scope_n, pid = _resolve_scope_project(session, scope, project_id)
    mode_norm = (mode or "replace").strip().lower()
    if mode_norm not in ("replace", "append"):
        raise ValueError("mode must be replace or append")

    doc = _active_brain_query(session, scope, project_id, rel).first()
    created = doc is None

    if doc is None:
        doc = BrainDocument(scope=scope_n, project_id=pid, relative_path=rel, content="")
        session.add(doc)
        session.flush()

    if mode_norm == "append" and doc.content:
        new_content = doc.content.rstrip() + "\n\n" + (content or "")
    else:
        new_content = content or ""

    if not created and doc.content != new_content:
        _save_brain_revision(session, doc)

    doc.content = new_content
    doc.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()
    session.refresh(doc)

    result = brain_doc_to_dict(doc)
    result["storage"] = "postgres"
    result["mode"] = mode_norm
    result["created"] = created
    return result


def soft_delete_brain(
    session: Session,
    *,
    scope: str,
    relative_path: str,
    project_id: int | None = None,
) -> dict[str, Any]:
    rel = safe_relative_brain_path(relative_path)
    if not rel:
        raise ValueError("Invalid brain path")

    doc = _active_brain_query(session, scope, project_id, rel).first()
    if not doc:
        raise ValueError(f"Brain file not found: {rel}")

    _save_brain_revision(session, doc)
    doc.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()
    return {"ok": True, "id": doc.id, "relative_path": rel, "soft_deleted": True}


def restore_brain(
    session: Session,
    *,
    scope: str,
    relative_path: str,
    project_id: int | None = None,
) -> dict[str, Any]:
    rel = safe_relative_brain_path(relative_path)
    if not rel:
        raise ValueError("Invalid brain path")

    scope_n, pid = _resolve_scope_project(session, scope, project_id)
    q = session.query(BrainDocument).filter(
        BrainDocument.scope == scope_n,
        BrainDocument.relative_path == rel,
        BrainDocument.deleted_at.isnot(None),
    )
    if scope_n == "global":
        q = q.filter(BrainDocument.project_id.is_(None))
    else:
        q = q.filter(BrainDocument.project_id == pid)

    doc = q.order_by(BrainDocument.deleted_at.desc()).first()
    if not doc:
        raise ValueError(f"No deleted brain file to restore: {rel}")

    conflict = _active_brain_query(session, scope, project_id, rel).first()
    if conflict:
        raise ValueError(f"An active brain file already exists at {rel}; delete or rename it first")

    doc.deleted_at = None
    session.commit()
    return brain_doc_to_dict(doc)


def list_brain_revisions(
    session: Session,
    *,
    scope: str,
    relative_path: str,
    project_id: int | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rel = safe_relative_brain_path(relative_path)
    if not rel:
        raise ValueError("Invalid brain path")

    doc = _active_brain_query(session, scope, project_id, rel).first()
    if not doc:
        doc = (
            session.query(BrainDocument)
            .filter(BrainDocument.relative_path == rel)
            .order_by(BrainDocument.updated_at.desc())
            .first()
        )
    if not doc:
        return []

    cap = max(1, min(int(limit), 100))
    rows = (
        session.query(BrainDocumentRevision)
        .filter(BrainDocumentRevision.brain_document_id == doc.id)
        .order_by(BrainDocumentRevision.revision_number.desc())
        .limit(cap)
        .all()
    )
    return [
        {
            "revision_number": r.revision_number,
            "relative_path": r.relative_path,
            "content_preview": (r.content[:400] + "…") if len(r.content) > 400 else r.content,
            "content_length": len(r.content),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
