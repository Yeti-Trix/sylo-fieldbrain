#!/usr/bin/env python3
"""Soft-delete a brain document (logicscout_brain_delete tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.brain_service import soft_delete_brain
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--scope", choices=("global", "project"), default="project")
    parser.add_argument("--project-id", type=int, default=None)
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    if args.scope == "project" and args.project_id is None:
        emit_error("--project-id is required when scope is project")

    try:
        with Session(get_engine()) as session:
            result = soft_delete_brain(
                session,
                scope=args.scope,
                relative_path=args.path,
                project_id=args.project_id,
            )
    except ValueError as exc:
        emit_error(str(exc))

    emit(
        {
            "ok": True,
            **result,
            "operator_chat": f"Soft-deleted brain {args.scope}:{args.path} (revision saved).",
        }
    )


if __name__ == "__main__":
    main()
