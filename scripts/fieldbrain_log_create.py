#!/usr/bin/env python3
"""Create a maintenance log entry (logicscout_log_create tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.maintenance_log_service import create_log_entry
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True, help="Short summary title")
    parser.add_argument("--body", required=True, help="Full log body / notes")
    parser.add_argument("--project-id", type=int, default=None, help="Optional project id")
    parser.add_argument("--fault-code", default="", help="Optional fault/alarm code")
    parser.add_argument("--equipment-tag", default="", help="Optional PLC/HMI tag or asset id")
    parser.add_argument("--logged-by", default="", help="Optional attribution string")
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    try:
        with Session(get_engine()) as session:
            entry = create_log_entry(
                session,
                title=args.title,
                body=args.body,
                project_id=args.project_id,
                fault_code=args.fault_code or None,
                equipment_tag=args.equipment_tag or None,
                logged_by=args.logged_by or None,
            )
    except ValueError as exc:
        emit_error(str(exc))

    emit(
        {
            "ok": True,
            "entry": entry,
            "operator_chat": (
                f"Logged maintenance entry #{entry['id']}: {entry['title']}"
                + (f" (project {entry['project_id']})" if entry.get("project_id") else "")
            ),
        }
    )


if __name__ == "__main__":
    main()
