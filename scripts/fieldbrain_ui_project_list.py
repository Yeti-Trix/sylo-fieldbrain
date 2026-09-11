#!/usr/bin/env python3
"""List projects with stats for FieldBrain dashboard (fieldbrain:projectList IPC)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.project_service import list_projects_with_stats
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-hidden", action="store_true", help="Include system-hidden projects")
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    with Session(get_engine()) as session:
        projects = list_projects_with_stats(session, include_hidden=args.include_hidden)

    lines = []
    for p in projects:
        stats = p.get("stats") or {}
        lines.append(
            f"{p['id']}: {p['name']} — "
            f"{stats.get('brain_entries', 0)} brain, "
            f"{stats.get('library_docs', 0)} docs, "
            f"{stats.get('maintenance_logs', 0)} logs"
        )

    emit(
        {
            "ok": True,
            "count": len(projects),
            "projects": projects,
            "operator_chat": (
                f"Found {len(projects)} project(s).\n" + ("\n".join(lines) if lines else "(none)")
            ),
        }
    )


if __name__ == "__main__":
    main()
