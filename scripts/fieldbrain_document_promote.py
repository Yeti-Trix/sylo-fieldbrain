#!/usr/bin/env python3
"""Promote a project-local document to the global library (fieldbrain_document_promote tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.document_service import promote_document_to_global
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", type=int, required=True, help="Document id to promote")
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    try:
        with Session(get_engine()) as session:
            result = promote_document_to_global(session, args.document_id)
    except ValueError as exc:
        emit_error(str(exc))

    doc = result["document"]
    if result.get("promoted"):
        chat = (
            f"Promoted document #{doc['id']} ({doc['title']}) to the global library. "
            f"It now appears in global search; the link to project "
            f"{result.get('previous_project_id')} is kept."
        )
    else:
        chat = f"Document #{doc['id']} ({doc['title']}) is already in the global library."

    emit({"ok": True, **result, "operator_chat": chat})


if __name__ == "__main__":
    main()
