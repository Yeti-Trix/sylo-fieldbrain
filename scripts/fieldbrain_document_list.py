#!/usr/bin/env python3
"""List global or project documents (logicscout_document_list tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.document_service import list_documents_for_project, list_global_documents
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope",
        choices=("global", "project"),
        default="global",
        help="global library or project-attached documents",
    )
    parser.add_argument("--project-id", type=int, default=None, help="Required when scope=project")
    parser.add_argument("--category", default="", help="Filter global docs by category")
    parser.add_argument("--search", default="", help="Filter global docs by title/filename")
    parser.add_argument("--limit", type=int, default=200, help="Max global results (default 200)")
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    if args.scope == "project" and args.project_id is None:
        emit_error("--project-id is required when scope is project")

    with Session(get_engine()) as session:
        if args.scope == "global":
            documents = list_global_documents(
                session,
                category=args.category or None,
                search=args.search or None,
                limit=args.limit,
            )
        else:
            documents = list_documents_for_project(session, args.project_id)

    lines = []
    for d in documents:
        role = f" role={d['link_role']}" if d.get("link_role") else ""
        lines.append(f"#{d['id']} {d['title']} ({d['scope']}){role}")

    emit(
        {
            "ok": True,
            "scope": args.scope,
            "project_id": args.project_id,
            "count": len(documents),
            "documents": documents,
            "operator_chat": (
                f"Listed {len(documents)} document(s) ({args.scope}).\n"
                + ("\n".join(lines) if lines else "(none)")
            ),
        }
    )


if __name__ == "__main__":
    main()
