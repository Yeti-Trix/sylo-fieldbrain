"""Maintenance log CRUD, search, soft delete, and revision history."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models import MaintenanceLogEntry, MaintenanceLogRevision, Project


def log_entry_to_dict(entry: MaintenanceLogEntry, *, project_name: str | None = None) -> dict[str, Any]:
    return {
        "id": entry.id,
        "project_id": entry.project_id,
        "project_name": project_name,
        "title": entry.title,
        "body": entry.body,
        "fault_code": entry.fault_code,
        "equipment_tag": entry.equipment_tag,
        "logged_by": entry.logged_by,
        "deleted_at": entry.deleted_at.isoformat() if entry.deleted_at else None,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


def _active_logs_query(session: Session):
    return session.query(MaintenanceLogEntry, Project.name).outerjoin(
        Project, MaintenanceLogEntry.project_id == Project.id
    ).filter(MaintenanceLogEntry.deleted_at.is_(None))


def _next_log_revision(session: Session, entry_id: int) -> int:
    current = (
        session.query(func.max(MaintenanceLogRevision.revision_number))
        .filter(MaintenanceLogRevision.log_entry_id == entry_id)
        .scalar()
    )
    return int(current or 0) + 1


def _save_log_revision(session: Session, entry: MaintenanceLogEntry) -> None:
    rev = MaintenanceLogRevision(
        log_entry_id=entry.id,
        title=entry.title,
        body=entry.body,
        fault_code=entry.fault_code,
        equipment_tag=entry.equipment_tag,
        logged_by=entry.logged_by,
        revision_number=_next_log_revision(session, entry.id),
    )
    session.add(rev)


def create_log_entry(
    session: Session,
    *,
    title: str,
    body: str,
    project_id: int | None = None,
    fault_code: str | None = None,
    equipment_tag: str | None = None,
    logged_by: str | None = None,
) -> dict[str, Any]:
    clean_title = title.strip()
    clean_body = body.strip()
    if not clean_title:
        raise ValueError("title is required")
    if not clean_body:
        raise ValueError("body is required")

    project_name = None
    if project_id is not None:
        project = session.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")
        project_name = project.name

    entry = MaintenanceLogEntry(
        project_id=project_id,
        title=clean_title,
        body=clean_body,
        fault_code=(fault_code or "").strip() or None,
        equipment_tag=(equipment_tag or "").strip() or None,
        logged_by=(logged_by or "").strip() or None,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return log_entry_to_dict(entry, project_name=project_name)


def update_log_entry(
    session: Session,
    entry_id: int,
    *,
    title: str | None = None,
    body: str | None = None,
    fault_code: str | None = None,
    equipment_tag: str | None = None,
    logged_by: str | None = None,
) -> dict[str, Any]:
    entry = (
        session.query(MaintenanceLogEntry)
        .filter(MaintenanceLogEntry.id == entry_id, MaintenanceLogEntry.deleted_at.is_(None))
        .first()
    )
    if not entry:
        raise ValueError(f"Log entry {entry_id} not found")

    _save_log_revision(session, entry)

    if title is not None and title.strip():
        entry.title = title.strip()
    if body is not None and body.strip():
        entry.body = body.strip()
    if fault_code is not None:
        entry.fault_code = fault_code.strip() or None
    if equipment_tag is not None:
        entry.equipment_tag = equipment_tag.strip() or None
    if logged_by is not None:
        entry.logged_by = logged_by.strip() or None

    entry.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()
    session.refresh(entry)

    project_name = None
    if entry.project_id:
        proj = session.query(Project).filter(Project.id == entry.project_id).first()
        project_name = proj.name if proj else None
    return log_entry_to_dict(entry, project_name=project_name)


def soft_delete_log_entry(session: Session, entry_id: int) -> dict[str, Any]:
    entry = (
        session.query(MaintenanceLogEntry)
        .filter(MaintenanceLogEntry.id == entry_id, MaintenanceLogEntry.deleted_at.is_(None))
        .first()
    )
    if not entry:
        raise ValueError(f"Log entry {entry_id} not found")

    _save_log_revision(session, entry)
    entry.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()
    return {"ok": True, "id": entry_id, "soft_deleted": True}


def restore_log_entry(session: Session, entry_id: int) -> dict[str, Any]:
    entry = (
        session.query(MaintenanceLogEntry)
        .filter(MaintenanceLogEntry.id == entry_id, MaintenanceLogEntry.deleted_at.isnot(None))
        .first()
    )
    if not entry:
        raise ValueError(f"No deleted log entry {entry_id} to restore")

    entry.deleted_at = None
    session.commit()
    session.refresh(entry)

    project_name = None
    if entry.project_id:
        proj = session.query(Project).filter(Project.id == entry.project_id).first()
        project_name = proj.name if proj else None
    return log_entry_to_dict(entry, project_name=project_name)


def list_log_revisions(session: Session, entry_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
    cap = max(1, min(int(limit), 100))
    rows = (
        session.query(MaintenanceLogRevision)
        .filter(MaintenanceLogRevision.log_entry_id == entry_id)
        .order_by(MaintenanceLogRevision.revision_number.desc())
        .limit(cap)
        .all()
    )
    return [
        {
            "revision_number": r.revision_number,
            "title": r.title,
            "body_preview": (r.body[:400] + "…") if len(r.body) > 400 else r.body,
            "fault_code": r.fault_code,
            "equipment_tag": r.equipment_tag,
            "logged_by": r.logged_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def search_log_entries(
    session: Session,
    *,
    query: str,
    project_id: int | None = None,
    fault_code: str | None = None,
    equipment_tag: str | None = None,
    limit: int = 25,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    term = (query or "").strip()
    cap = max(1, min(int(limit), 100))

    base = session.query(MaintenanceLogEntry, Project.name).outerjoin(
        Project, MaintenanceLogEntry.project_id == Project.id
    )
    if not include_deleted:
        base = base.filter(MaintenanceLogEntry.deleted_at.is_(None))

    if project_id is not None:
        base = base.filter(MaintenanceLogEntry.project_id == project_id)
    if fault_code and fault_code.strip():
        base = base.filter(MaintenanceLogEntry.fault_code.ilike(fault_code.strip()))
    if equipment_tag and equipment_tag.strip():
        base = base.filter(MaintenanceLogEntry.equipment_tag.ilike(f"%{equipment_tag.strip()}%"))

    if term:
        ts_query = func.plainto_tsquery("english", term)
        ranked = base.filter(MaintenanceLogEntry.search_vector.op("@@")(ts_query)).order_by(
            func.ts_rank_cd(MaintenanceLogEntry.search_vector, ts_query).desc(),
            MaintenanceLogEntry.created_at.desc(),
        )
        rows = ranked.limit(cap).all()
        if rows:
            return [log_entry_to_dict(entry, project_name=name) for entry, name in rows]

        like = f"%{term}%"
        fallback = base.filter(
            or_(
                MaintenanceLogEntry.title.ilike(like),
                MaintenanceLogEntry.body.ilike(like),
                MaintenanceLogEntry.fault_code.ilike(like),
                MaintenanceLogEntry.equipment_tag.ilike(like),
            )
        ).order_by(MaintenanceLogEntry.created_at.desc())
        rows = fallback.limit(cap).all()
        return [log_entry_to_dict(entry, project_name=name) for entry, name in rows]

    rows = base.order_by(MaintenanceLogEntry.created_at.desc()).limit(cap).all()
    return [log_entry_to_dict(entry, project_name=name) for entry, name in rows]


def get_log_entry(session: Session, entry_id: int, *, include_deleted: bool = False) -> dict[str, Any] | None:
    q = session.query(MaintenanceLogEntry, Project.name).outerjoin(
        Project, MaintenanceLogEntry.project_id == Project.id
    ).filter(MaintenanceLogEntry.id == entry_id)
    if not include_deleted:
        q = q.filter(MaintenanceLogEntry.deleted_at.is_(None))
    row = q.first()
    if not row:
        return None
    entry, name = row
    return log_entry_to_dict(entry, project_name=name)
