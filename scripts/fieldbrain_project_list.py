#!/usr/bin/env python3
"""List LogicScout projects (logicscout_project_list tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.project_service import list_projects, list_projects_with_stats
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-hidden", action="store_true", help="Include system-hidden projects")
    parser.add_argument("--with-stats", action="store_true", help="Include brain/doc/log counts per project")
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    with Session(get_engine()) as session:
        if args.with_stats:
            projects = list_projects_with_stats(session, include_hidden=args.include_hidden)
        else:
            projects = list_projects(session, include_hidden=args.include_hidden)

    lines = []
    for p in projects:
        if args.with_stats and p.get("stats"):
            s = p["stats"]
            lines.append(
                f"{p['id']}: {p['name']} — {s.get('brain_entries', 0)} brain, "
                f"{s.get('library_docs', 0)} docs, {s.get('maintenance_logs', 0)} logs"
            )
        else:
            lines.append(f"{p['id']}: {p['name']}")
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
