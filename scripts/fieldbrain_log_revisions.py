#!/usr/bin/env python3
"""List revision history for a maintenance log entry (logicscout_log_revisions tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.maintenance_log_service import list_log_revisions
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entry-id", type=int, required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    with Session(get_engine()) as session:
        revisions = list_log_revisions(session, args.entry_id, limit=args.limit)

    emit(
        {
            "ok": True,
            "entry_id": args.entry_id,
            "revisions": revisions,
            "count": len(revisions),
            "operator_chat": f"{len(revisions)} revision(s) for log entry {args.entry_id}.",
        }
    )


if __name__ == "__main__":
    main()
