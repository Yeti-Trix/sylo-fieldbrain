#!/usr/bin/env python3
"""List revision history for a brain document (logicscout_brain_revisions tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.brain_service import list_brain_revisions
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--scope", choices=("global", "project"), default="project")
    parser.add_argument("--project-id", type=int, default=None)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    if args.scope == "project" and args.project_id is None:
        emit_error("--project-id is required when scope is project")

    try:
        with Session(get_engine()) as session:
            revisions = list_brain_revisions(
                session,
                scope=args.scope,
                relative_path=args.path,
                project_id=args.project_id,
                limit=args.limit,
            )
    except ValueError as exc:
        emit_error(str(exc))

    emit(
        {
            "ok": True,
            "path": args.path,
            "scope": args.scope,
            "revisions": revisions,
            "count": len(revisions),
            "operator_chat": f"{len(revisions)} revision(s) for brain {args.scope}:{args.path}.",
        }
    )


if __name__ == "__main__":
    main()
