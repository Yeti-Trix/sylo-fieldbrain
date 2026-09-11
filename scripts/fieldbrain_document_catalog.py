#!/usr/bin/env python3
"""Catalog a library document after the agent reads it with Sylo reader skills."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.document_catalog import catalog_document
from services.document_formats import READER_HINTS, reader_hint_for_ext
from services.document_service import register_document_from_path
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", type=int, default=None, help="Existing document id")
    parser.add_argument(
        "--file-path",
        default="",
        help="Register this file first (global or project scope), then catalog",
    )
    parser.add_argument(
        "--description",
        required=True,
        help="Agent-written catalog summary (what this file is and when to use it)",
    )
    parser.add_argument("--title", default="", help="Optional display title")
    parser.add_argument("--category", default="", help="manual, datasheet, requirements, email, howto, image, …")
    parser.add_argument("--tags", default="", help="Comma-separated or JSON array")
    parser.add_argument("--manufacturer", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--version", default="")
    parser.add_argument(
        "--outline-json",
        default="",
        help='Optional JSON array: [{"level":1,"title":"Section","page":0}]',
    )
    parser.add_argument(
        "--scope",
        choices=("global", "project"),
        default="global",
        help="When using --file-path (default global library)",
    )
    parser.add_argument("--project-id", type=int, default=None)
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    has_doc = args.document_id is not None
    has_file = bool(args.file_path.strip())
    if has_doc == has_file:
        emit_error("Provide exactly one of --document-id or --file-path")

    outline: list[dict] | None = None
    if args.outline_json.strip():
        try:
            parsed = json.loads(args.outline_json)
            if not isinstance(parsed, list):
                emit_error("--outline-json must be a JSON array")
            outline = parsed
        except json.JSONDecodeError as exc:
            emit_error(f"Invalid --outline-json: {exc}")

    try:
        with Session(get_engine()) as session:
            if has_file:
                path = Path(args.file_path.strip()).expanduser().resolve()
                ext = path.suffix.lower()
                reg = register_document_from_path(
                    session,
                    path,
                    scope=args.scope,
                    project_id=args.project_id,
                    title=args.title or None,
                    category=args.category or "other",
                    attach=args.project_id is not None,
                )
                doc_id = int(reg["document"]["id"])
                reader = reader_hint_for_ext(ext)
            else:
                doc_id = int(args.document_id)
                reader = None

            result = catalog_document(
                session,
                doc_id,
                description=args.description,
                tags=args.tags or None,
                category=args.category or None,
                title=args.title or None,
                manufacturer=args.manufacturer or None,
                model=args.model or None,
                version=args.version or None,
                outline=outline,
                project_id=args.project_id,
            )
    except ValueError as exc:
        emit_error(str(exc))
    except Exception as exc:
        emit_error(f"Catalog failed: {exc}")

    doc = result["document"]
    lines = [
        f"Cataloged document #{doc['id']}: {doc['title']} (category={doc['category']}).",
        f"Indexed {result.get('chunks_indexed', 0)} search chunk(s); "
        f"{result.get('embeddings_written', 0)} embedding(s).",
        "Deep read later with the matching Sylo reader — not stored as full-text chunks.",
    ]
    if reader:
        lines.insert(1, f"Reader for this type: {reader}")
    emit(
        {
            "ok": True,
            **result,
            "reader_hints": READER_HINTS,
            "operator_chat": "\n".join(lines),
        }
    )


if __name__ == "__main__":
    main()
