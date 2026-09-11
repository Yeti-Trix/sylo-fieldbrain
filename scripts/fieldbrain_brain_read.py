#!/usr/bin/env python3
"""Read brain markdown (logicscout_brain_read tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.brain_service import read_brain_markdown
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="Relative brain path, e.g. gotchas/conveyor_jam.md")
    parser.add_argument(
        "--scope",
        choices=("global", "project"),
        default="project",
        help="global org brain or project brain",
    )
    parser.add_argument("--project-id", type=int, default=None, help="Required when scope=project")
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    if args.scope == "project" and args.project_id is None:
        emit_error("--project-id is required when scope is project")

    try:
        with Session(get_engine()) as session:
            result = read_brain_markdown(
                session,
                scope=args.scope,
                relative_path=args.path,
                project_id=args.project_id,
            )
    except ValueError as exc:
        emit_error(str(exc))

    preview = result["content"]
    if len(preview) > 1200:
        preview = preview[:1200] + "\n… (truncated in chat; full content in JSON)"

    emit(
        {
            "ok": True,
            **result,
            "operator_chat": (
                f"Brain {result['scope']}:{result['relative_path']} "
                f"({result['size_bytes']} bytes)\n\n{preview}"
            ),
        }
    )


if __name__ == "__main__":
    main()
