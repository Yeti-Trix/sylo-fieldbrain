#!/usr/bin/env python3
"""Attach existing doc or register new file path (logicscout_document_attach tool)."""

from __future__ import annotations

import argparse
from pathlib import Path

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.document_service import attach_document_to_project, register_document_from_path
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", type=int, default=None, help="Attach existing document by id")
    parser.add_argument("--file-path", default="", help="Register a new file (copied into shared storage)")
    parser.add_argument("--project-id", type=int, default=None, help="Target project id")
    parser.add_argument(
        "--scope",
        choices=("global", "project"),
        default="project",
        help="Scope when registering a new file (default project)",
    )
    parser.add_argument("--title", default="", help="Optional title when registering a file")
    parser.add_argument("--role", default="reference", help="Link role: reference or schematic")
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    has_doc = args.document_id is not None
    has_file = bool(args.file_path.strip())
    if has_doc == has_file:
        emit_error("Provide exactly one of --document-id or --file-path")

    try:
        with Session(get_engine()) as session:
            if has_file:
                result = register_document_from_path(
                    session,
                    Path(args.file_path.strip()),
                    scope=args.scope,
                    project_id=args.project_id,
                    title=args.title or None,
                    attach=args.project_id is not None,
                )
                doc = result["document"]
                chat = (
                    f"Registered document #{doc['id']}: {doc['title']} "
                    f"(scope={doc['scope']}, created={result['created']})."
                )
                if result.get("linked"):
                    chat += f" Linked to project {args.project_id}."
                emit({"ok": True, **result, "operator_chat": chat})
            else:
                if args.project_id is None:
                    emit_error("--project-id is required when attaching an existing document")
                result = attach_document_to_project(
                    session,
                    args.project_id,
                    args.document_id,
                    role=args.role,
                )
                doc = result["document"]
                verb = "Attached" if not result.get("already_linked") else "Already linked"
                emit(
                    {
                        "ok": True,
                        **result,
                        "operator_chat": f"{verb} document #{doc['id']} ({doc['title']}) to project {args.project_id}.",
                    }
                )
    except ValueError as exc:
        emit_error(str(exc))


if __name__ == "__main__":
    main()
