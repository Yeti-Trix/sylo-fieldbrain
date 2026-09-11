#!/usr/bin/env python3
"""List brain markdown files for FieldBrain dashboard."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.brain_service import list_brain_documents
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope",
        choices=("global", "project"),
        default="project",
        help="global org brain or project brain",
    )
    parser.add_argument("--project-id", type=int, default=None, help="Required when scope=project")
    parser.add_argument("--search", default="", help="Filter by path substring")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    if args.scope == "project" and args.project_id is None:
        emit_error("--project-id is required when scope is project")

    with Session(get_engine()) as session:
        brains = list_brain_documents(
            session,
            scope=args.scope,
            project_id=args.project_id,
            search=args.search or None,
            limit=args.limit,
        )

    lines = [f"#{b['id']} {b['relative_path']}" for b in brains]
    emit(
        {
            "ok": True,
            "scope": args.scope,
            "project_id": args.project_id,
            "count": len(brains),
            "brains": brains,
            "operator_chat": (
                f"Listed {len(brains)} brain file(s) ({args.scope}).\n"
                + ("\n".join(lines) if lines else "(none)")
            ),
        }
    )


if __name__ == "__main__":
    main()
