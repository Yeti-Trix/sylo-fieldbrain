#!/usr/bin/env python3
"""Create a project from FieldBrain dashboard (fieldbrain:projectCreate IPC)."""

from __future__ import annotations

import argparse
import json

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.brain_paths import ensure_project_brain_layout
from services.project_service import create_project_structured
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-number", default="", help="Five-digit project number (e.g. 12345)")
    parser.add_argument(
        "--sub-project-number",
        default="",
        help="Optional three-digit sub-project (e.g. 001) → creates 12345-001",
    )
    parser.add_argument("--name", default="", help="Legacy: full name 12345 or 12345-001")
    parser.add_argument(
        "--tags-json",
        default="",
        help='JSON array of tag strings, e.g. ["line3"]',
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

    job_number = args.job_number.strip()
    sub_number = args.sub_project_number.strip()
    legacy_name = args.name.strip()

    if legacy_name and not job_number:
        from services.project_naming import parse_project_name

        job, suffix = parse_project_name(legacy_name)
        if not job:
            emit_error("Provide --job-number (12345) or legacy --name in 12345 / 12345-001 format.")
        job_number = job
        sub_number = suffix or ""

    if not job_number:
        emit_error("Project number is required (five digits, e.g. 12345).")

    try:
        with Session(get_engine()) as session:
            project = create_project_structured(
                session,
                job_number=job_number,
                sub_project_number=sub_number or None,
                project_tags=tags,
            )
        ensure_project_brain_layout(project["id"])
        if project.get("parent_job_id"):
            ensure_project_brain_layout(int(project["parent_job_id"]))
    except ValueError as exc:
        emit_error(str(exc))

    if project["level"] == "sub_project":
        chat = (
            f"Created sub-project {project['id']}: {project['name']} "
            f"(under project {project.get('job_number')})."
        )
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
