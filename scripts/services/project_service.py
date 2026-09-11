"""Project CRUD helpers for sylo-fieldbrain."""

from __future__ import annotations

import json
from typing import Any, Literal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models import (
    BrainDocument,
    Document,
    MaintenanceLogEntry,
    Project,
    ProjectDocumentLink,
)
from services.project_naming import (
    JOB_PATTERN,
    SUBJOB_PATTERN,
    compose_subproject_name,
    normalize_digits,
    parse_job_number,
    parse_project_name,
    validate_job_number,
    validate_subproject_number,
)


def _project_tags_list(project: Project) -> list[str]:
    raw = getattr(project, "project_tags_json", None)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data if str(x).strip()]
    except json.JSONDecodeError:
        pass
    return []


def _project_level(project: Project) -> Literal["job", "sub_project", "other"]:
    name = project.name or ""
    if project.parent_project_id is not None or SUBJOB_PATTERN.match(name):
        return "sub_project"
    if JOB_PATTERN.match(name):
        return "job"
    return "other"


def project_to_dict(project: Project, *, stats: dict[str, int] | None = None) -> dict[str, Any]:
    level = _project_level(project)
    out: dict[str, Any] = {
        "id": project.id,
        "name": project.name,
        "job_number": project.job_number,
        "parent_project_id": project.parent_project_id,
        "level": level,
        "controller_name": project.controller_name,
        "processor_type": project.processor_type,
        "software_revision": project.software_revision,
        "l5x_file_path": project.l5x_file_path,
        "l5x_file_hash": project.l5x_file_hash,
        "plc_ip": project.plc_ip,
        "plc_read_enabled": bool(project.plc_read_enabled),
        "org_id": project.org_id or "default",
        "project_tags": _project_tags_list(project),
        "l5x_status": project.l5x_status or "analyzed",
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }
    if stats is not None:
        out["stats"] = stats
    return out


def find_project_by_name(session: Session, name: str, *, org_id: str = "default") -> Project | None:
    clean = normalize_digits(name)
    if not clean:
        return None
    return (
        session.query(Project)
        .filter(
            Project.org_id == (org_id or "default"),
            func.lower(Project.name) == clean.lower(),
        )
        .first()
    )


def find_job_project(session: Session, job_number: str, *, org_id: str = "default") -> Project | None:
    return find_project_by_name(session, job_number, org_id=org_id)


def _brain_counts(session: Session) -> dict[int, int]:
    rows = (
        session.query(BrainDocument.project_id, func.count(BrainDocument.id))
        .filter(
            BrainDocument.deleted_at.is_(None),
            BrainDocument.scope == "project",
            BrainDocument.project_id.isnot(None),
        )
        .group_by(BrainDocument.project_id)
        .all()
    )
    return {int(pid): int(count) for pid, count in rows if pid is not None}


def _log_counts(session: Session) -> dict[int, int]:
    rows = (
        session.query(MaintenanceLogEntry.project_id, func.count(MaintenanceLogEntry.id))
        .filter(
            MaintenanceLogEntry.deleted_at.is_(None),
            MaintenanceLogEntry.project_id.isnot(None),
        )
        .group_by(MaintenanceLogEntry.project_id)
        .all()
    )
    return {int(pid): int(count) for pid, count in rows if pid is not None}


def _library_doc_counts(session: Session) -> dict[int, int]:
    linked = (
        session.query(
            ProjectDocumentLink.project_id.label("pid"),
            ProjectDocumentLink.document_id.label("doc_id"),
        )
        .join(Document, Document.id == ProjectDocumentLink.document_id)
        .filter(Document.archived.is_(False))
    )
    owned = session.query(
        Document.owner_project_id.label("pid"),
        Document.id.label("doc_id"),
    ).filter(
        Document.archived.is_(False),
        Document.scope == "project_local",
        Document.owner_project_id.isnot(None),
    )
    combined = linked.union_all(owned).subquery()
    rows = (
        session.query(combined.c.pid, func.count(func.distinct(combined.c.doc_id)))
        .group_by(combined.c.pid)
        .all()
    )
    return {int(pid): int(count) for pid, count in rows if pid is not None}


def _stats_for_projects(session: Session, project_ids: list[int]) -> dict[int, dict[str, int]]:
    if not project_ids:
        return {}
    brains = _brain_counts(session)
    logs = _log_counts(session)
    docs = _library_doc_counts(session)
    out: dict[int, dict[str, int]] = {}
    for pid in project_ids:
        out[pid] = {
            "brain_entries": brains.get(pid, 0),
            "library_docs": docs.get(pid, 0),
            "maintenance_logs": logs.get(pid, 0),
        }
    return out


def _sort_projects(projects: list[Project]) -> list[Project]:
    def key(p: Project) -> tuple[str, int, str]:
        job = p.job_number or "zzzzz"
        level_rank = 0 if _project_level(p) == "job" else 1
        return (job, level_rank, p.name or "")

    return sorted(projects, key=key)


def list_projects(session: Session, *, include_hidden: bool = False) -> list[dict[str, Any]]:
    query = session.query(Project)
    if not include_hidden:
        query = query.filter(or_(Project.is_system_hidden.is_(False), Project.is_system_hidden.is_(None)))
    return [project_to_dict(p) for p in _sort_projects(query.all())]


def list_projects_with_stats(session: Session, *, include_hidden: bool = False) -> list[dict[str, Any]]:
    query = session.query(Project)
    if not include_hidden:
        query = query.filter(or_(Project.is_system_hidden.is_(False), Project.is_system_hidden.is_(None)))
    projects = _sort_projects(query.all())
    ids = [p.id for p in projects]
    stats_map = _stats_for_projects(session, ids)
    empty = {"brain_entries": 0, "library_docs": 0, "maintenance_logs": 0}
    return [project_to_dict(p, stats=stats_map.get(p.id, empty)) for p in projects]


def get_project(session: Session, project_id: int) -> dict[str, Any] | None:
    project = session.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None
    stats = _stats_for_projects(session, [project.id]).get(project.id)
    return project_to_dict(project, stats=stats)


def _insert_project(
    session: Session,
    *,
    name: str,
    job_number: str,
    parent_project_id: int | None,
    project_tags: list[str] | None,
    org_id: str,
) -> Project:
    tags_json = None
    if project_tags:
        cleaned = [str(t).strip() for t in project_tags if str(t).strip()]
        if cleaned:
            tags_json = json.dumps(cleaned)

    project = Project(
        name=name[:255],
        job_number=job_number,
        parent_project_id=parent_project_id,
        project_tags_json=tags_json,
        org_id=org_id,
        l5x_status="pending",
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def ensure_job_project(
    session: Session,
    job_number: str,
    *,
    org_id: str = "default",
    project_tags: list[str] | None = None,
) -> tuple[Project, bool]:
    org = (org_id or "default").strip() or "default"
    existing = find_job_project(session, job_number, org_id=org)
    if existing:
        return existing, False
    project = _insert_project(
        session,
        name=job_number,
        job_number=job_number,
        parent_project_id=None,
        project_tags=project_tags,
        org_id=org,
    )
    return project, True


def create_project_structured(
    session: Session,
    *,
    job_number: str,
    sub_project_number: str | None = None,
    project_tags: list[str] | None = None,
    org_id: str = "default",
) -> dict[str, Any]:
    """Create job-level project (12345) and/or sub-project (12345-001)."""
    job = validate_job_number(job_number)
    org = (org_id or "default").strip() or "default"
    sub_raw = (sub_project_number or "").strip()

    if not sub_raw:
        existing = find_job_project(session, job, org_id=org)
        if existing:
            raise ValueError(
                f"Project {job!r} already exists (id={existing.id}). "
                "Use that id in chat or add a sub-project number."
            )
        project = _insert_project(
            session,
            name=job,
            job_number=job,
            parent_project_id=None,
            project_tags=project_tags,
            org_id=org,
        )
    else:
        suffix = validate_subproject_number(sub_raw, job_number=job)
        full_name = compose_subproject_name(job, suffix)
        existing = find_project_by_name(session, full_name, org_id=org)
        if existing:
            raise ValueError(
                f"Sub-project {full_name!r} already exists (id={existing.id}). "
                "Use that project or pick a different sub-project number."
            )
        parent, _ = ensure_job_project(session, job, org_id=org, project_tags=None)
        project = _insert_project(
            session,
            name=full_name,
            job_number=job,
            parent_project_id=parent.id,
            project_tags=project_tags,
            org_id=org,
        )

    result = project_to_dict(
        project,
        stats={"brain_entries": 0, "library_docs": 0, "maintenance_logs": 0},
    )
    if sub_raw:
        result["parent_job_id"] = project.parent_project_id
    else:
        result["created_job_project"] = True
    return result


def create_project(
    session: Session,
    *,
    name: str,
    domain: str | None = None,
    controller_family: str | None = None,
    project_tags: list[str] | None = None,
    org_id: str = "default",
) -> dict[str, Any]:
    """Agent/chat create by full name: 12345 or 12345-001."""
    clean_name = normalize_digits(name)
    if not clean_name:
        raise ValueError("Project name is required")

    job, suffix = parse_project_name(clean_name)
    if job and suffix:
        return create_project_structured(
            session,
            job_number=job,
            sub_project_number=suffix,
            project_tags=project_tags,
            org_id=org_id,
        )
    if job and not suffix:
        return create_project_structured(
            session,
            job_number=job,
            sub_project_number=None,
            project_tags=project_tags,
            org_id=org_id,
        )

    org = (org_id or "default").strip() or "default"
    existing = find_project_by_name(session, clean_name, org_id=org)
    if existing:
        raise ValueError(
            f"Project name {clean_name!r} already exists (id={existing.id}). "
            "Use five-digit job (12345) or sub-project (12345-001)."
        )

    project = _insert_project(
        session,
        name=clean_name[:255],
        job_number=parse_job_number(clean_name),
        parent_project_id=None,
        project_tags=project_tags,
        org_id=org,
    )
    if domain or controller_family:
        if domain:
            project.domain = domain.strip() or None
        if controller_family:
            project.controller_family = controller_family.strip() or None
        session.commit()
        session.refresh(project)

    return project_to_dict(
        project,
        stats={"brain_entries": 0, "library_docs": 0, "maintenance_logs": 0},
    )
