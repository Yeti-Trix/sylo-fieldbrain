#!/usr/bin/env python3
"""Hybrid search across project knowledge (logicscout_search tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.search_service import hybrid_search
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-id",
        type=int,
        default=None,
        help="Project to search (project + global). Omit for global-only search.",
    )
    parser.add_argument("--query", required=True, help="Search query text")
    parser.add_argument("--limit", type=int, default=25, help="Max results (default 25)")
    parser.add_argument(
        "--source-type",
        default="",
        help="Optional filter: document, brain, tag, rung, etc.",
    )
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    with Session(get_engine()) as session:
        results = hybrid_search(
            session,
            args.project_id,
            args.query,
            limit=args.limit,
            source_type=args.source_type or None,
        )

    lines = []
    for r in results:
        scope_tag = "global" if r.get("scope") == "global" else f"project {r.get('project_id')}"
        lines.append(
            f"[{r['score']}] ({scope_tag}) #{r['id']} {r['type']} {r['label']}: {r['snippet'][:160]}"
        )

    where = (
        f"project {args.project_id} + global library/brain"
        if args.project_id is not None
        else "global library/brain only"
    )
    emit(
        {
            "ok": True,
            "project_id": args.project_id,
            "search_scope": "project_plus_global" if args.project_id is not None else "global_only",
            "query": args.query,
            "count": len(results),
            "results": results,
            "operator_chat": (
                f"Search ({where}) for {args.query!r}: "
                f"{len(results)} hit(s).\n"
                + ("\n".join(lines) if lines else "(none)")
            ),
        }
    )


if __name__ == "__main__":
    main()
