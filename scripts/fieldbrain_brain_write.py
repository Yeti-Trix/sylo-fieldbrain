#!/usr/bin/env python3
"""Write/update brain markdown (logicscout_brain_write tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.brain_service import write_brain_markdown
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="Relative brain path, e.g. gotchas/conveyor_jam.md")
    parser.add_argument("--content", required=True, help="Markdown body (full file when mode=replace)")
    parser.add_argument(
        "--scope",
        choices=("global", "project"),
        default="project",
        help="global org brain or project brain",
    )
    parser.add_argument("--project-id", type=int, default=None, help="Required when scope=project")
    parser.add_argument(
        "--mode",
        choices=("replace", "append"),
        default="replace",
        help="replace entire file or append to existing",
    )
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    if args.scope == "project" and args.project_id is None:
        emit_error("--project-id is required when scope is project")

    try:
        with Session(get_engine()) as session:
            result = write_brain_markdown(
                session,
                scope=args.scope,
                relative_path=args.path,
                content=args.content,
                project_id=args.project_id,
                mode=args.mode,
            )
    except ValueError as exc:
        emit_error(str(exc))

    action = "Created" if result.get("created") else "Updated"
    emit(
        {
            "ok": True,
            **result,
            "operator_chat": (
                f"{action} brain {result['scope']}:{result['relative_path']} "
                f"({result['size_bytes']} bytes, mode={result['mode']})."
            ),
        }
    )


if __name__ == "__main__":
    main()
