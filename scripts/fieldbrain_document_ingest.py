#!/usr/bin/env python3
"""Ingest PDF/text: extract, chunk, index, embed (logicscout_document_ingest tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.document_ingest import ingest_document_file
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file-path", required=True, help="Path to PDF or .txt on disk")
    parser.add_argument(
        "--scope",
        choices=("global", "project"),
        default="project",
        help="global library or project-local document",
    )
    parser.add_argument("--project-id", type=int, default=None, help="Required when scope=project")
    parser.add_argument("--title", default="", help="Optional document title")
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    if args.scope == "project" and args.project_id is None:
        emit_error("--project-id is required when scope is project")

    try:
        with Session(get_engine()) as session:
            result = ingest_document_file(
                session,
                args.file_path,
                scope=args.scope,
                project_id=args.project_id,
                title=args.title or None,
            )
    except ValueError as exc:
        emit_error(str(exc))
    except Exception as exc:
        emit_error(f"Ingest failed: {exc}")

    emit(
        {
            "ok": True,
            **result,
            "operator_chat": (
                f"Ingested document #{result['document_id']}: {result['title']}. "
                f"{result['chunks_indexed']} chunk(s) indexed, "
                f"{result['embeddings_written']} embedding(s) written."
            ),
        }
    )


if __name__ == "__main__":
    main()
