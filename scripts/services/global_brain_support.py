"""Org-level global brain shell project (hidden Projects row for search_index FK)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models import Project
from services.brain_paths import GLOBAL_BRAIN_PROJECT_NAME, ensure_global_brain_layout


def ensure_global_brain_shell_project(session: Session) -> Project:
    """Return or create the hidden project backing global/brain/ search rows."""
    project = session.query(Project).filter(Project.name == GLOBAL_BRAIN_PROJECT_NAME).first()
    if project:
        if not project.is_system_hidden:
            project.is_system_hidden = True
            session.commit()
            session.refresh(project)
        return project

    ensure_global_brain_layout()
    project = Project(
        name=GLOBAL_BRAIN_PROJECT_NAME,
        is_system_hidden=True,
        l5x_status="pending",
        org_id="default",
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def get_global_brain_shell_project_id(session: Session) -> int:
    """Database id for the global brain shell project."""
    return ensure_global_brain_shell_project(session).id
