#!/usr/bin/env python3
"""Soft-delete a maintenance log entry (logicscout_log_delete tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.maintenance_log_service import soft_delete_log_entry
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entry-id", type=int, required=True)
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    try:
        with Session(get_engine()) as session:
            result = soft_delete_log_entry(session, args.entry_id)
    except ValueError as exc:
        emit_error(str(exc))

    emit(
        {
            "ok": True,
            **result,
            "operator_chat": f"Soft-deleted maintenance log entry {args.entry_id} (revision saved).",
        }
    )


if __name__ == "__main__":
    main()
