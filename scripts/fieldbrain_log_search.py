#!/usr/bin/env python3
"""Search maintenance log entries (logicscout_log_search tool)."""

from __future__ import annotations

import argparse

from _db_lib import get_engine, verify_schema_version
from _json_out import emit, emit_error
from services.maintenance_log_service import search_log_entries
from sqlalchemy.orm import Session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="", help="Full-text search (title, body, fault, tag)")
    parser.add_argument("--project-id", type=int, default=None, help="Filter by project id")
    parser.add_argument("--fault-code", default="", help="Filter by fault code (substring)")
    parser.add_argument("--equipment-tag", default="", help="Filter by equipment tag (substring)")
    parser.add_argument("--limit", type=int, default=25, help="Max results (default 25)")
    args = parser.parse_args()

    ok, msg = verify_schema_version()
    if not ok:
        emit_error(msg)

    with Session(get_engine()) as session:
        entries = search_log_entries(
            session,
            query=args.query,
            project_id=args.project_id,
            fault_code=args.fault_code or None,
            equipment_tag=args.equipment_tag or None,
            limit=args.limit,
        )

    lines = []
    for e in entries:
        proj = f" [{e.get('project_name')}]" if e.get("project_name") else ""
        fault = f" fault={e['fault_code']}" if e.get("fault_code") else ""
        tag = f" tag={e['equipment_tag']}" if e.get("equipment_tag") else ""
        lines.append(f"#{e['id']} {e['title']}{proj}{fault}{tag}")

    emit(
        {
            "ok": True,
            "count": len(entries),
            "entries": entries,
            "operator_chat": (
                f"Found {len(entries)} log entr{'y' if len(entries) == 1 else 'ies'}.\n"
                + ("\n".join(lines) if lines else "(none)")
            ),
        }
    )


if __name__ == "__main__":
    main()
