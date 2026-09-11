#!/usr/bin/env python3
"""Create a LogicScout project (logicscout_project_create tool)."""

from __future__ import annotations

import argparse
import json

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.brain_paths import ensure_project_brain_layout
from services.project_service import create_project
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="12345 (job) or 12345-001 (sub-project)")
    parser.add_argument("--org-id", default="default", help="Org id (default: default)")
    parser.add_argument(
        "--tags-json",
        default="",
        help='JSON array of tag strings, e.g. ["line3","packaging"]',
    )
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    tags: list[str] | None = None
    if args.tags_json.strip():
        try:
            parsed = json.loads(args.tags_json)
            if isinstance(parsed, list):
                tags = [str(x) for x in parsed]
            else:
                emit_error("--tags-json must be a JSON array")
        except json.JSONDecodeError as exc:
            emit_error(f"Invalid --tags-json: {exc}")

    try:
        with Session(get_engine()) as session:
            project = create_project(
                session,
                name=args.name,
                project_tags=tags,
                org_id=args.org_id,
            )
        ensure_project_brain_layout(project["id"])
        if project.get("parent_project_id"):
            ensure_project_brain_layout(int(project["parent_project_id"]))
    except ValueError as exc:
        emit_error(str(exc))

    level = project.get("level", "other")
    if level == "sub_project":
        chat = f"Created sub-project {project['id']}: {project['name']} (under project {project.get('job_number')})."
    else:
        chat = f"Created project {project['id']}: {project['name']}."

    emit(
        {
            "ok": True,
            "project": project,
            "operator_chat": chat,
        }
    )


if __name__ == "__main__":
    main()
