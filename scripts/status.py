#!/usr/bin/env python3
"""Package status for fieldbrain_status tool."""

from __future__ import annotations

import argparse
from pathlib import Path

from _db_lib import connection_summary, package_root
from _json_out import emit


def main() -> None:
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    _ = args

    root = package_root()
    summary = connection_summary()

    emit(
        {
            "ok": True,
            "package_root": str(root),
            "shared_dir": str(root / "shared"),
            "scripts_dir": str(root / "scripts"),
            "operator_chat": (
                "FieldBrain package is enabled (LogicScout diagnostics included). "
                "Run fieldbrain_db_check to verify Postgres + pgvector + schema. "
                "Shared data lives in Postgres; Sylo private chats stay in SQLite. "
                "PLC L5X parse uses sylo-logicforge — LogicScout tools explore/index only."
            ),
            **summary,
        }
    )


if __name__ == "__main__":
    main()
