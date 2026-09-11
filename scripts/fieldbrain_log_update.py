#!/usr/bin/env python3
"""Update a maintenance log entry with revision history (logicscout_log_update tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.maintenance_log_service import update_log_entry
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entry-id", type=int, required=True)
    parser.add_argument("--title", default=None)
    parser.add_argument("--body", default=None)
    parser.add_argument("--fault-code", default=None)
    parser.add_argument("--equipment-tag", default=None)
    parser.add_argument("--logged-by", default=None)
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    try:
        with Session(get_engine()) as session:
            result = update_log_entry(
                session,
                args.entry_id,
                title=args.title,
                body=args.body,
                fault_code=args.fault_code,
                equipment_tag=args.equipment_tag,
                logged_by=args.logged_by,
            )
    except ValueError as exc:
        emit_error(str(exc))

    emit(
        {
            "ok": True,
            "entry": result,
            "operator_chat": f"Updated maintenance log entry {args.entry_id} (previous version saved to revisions).",
        }
    )


if __name__ == "__main__":
    main()
