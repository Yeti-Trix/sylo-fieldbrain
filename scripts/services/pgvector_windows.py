"""Windows pgvector file install + setup hints for FieldBrain."""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

PREBUILT_RELEASES_PAGE = "https://github.com/andreiramani/pgvector_pgsql_windows/releases"


def postgres_install_roots() -> list[tuple[int, Path]]:
    """Installed PostgreSQL directories under Program Files (Windows)."""
    roots: list[tuple[int, Path]] = []
    for base in (Path(r"C:\Program Files\PostgreSQL"), Path(r"C:\Program Files (x86)\PostgreSQL")):
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if child.is_dir() and child.name.isdigit():
                roots.append((int(child.name), child))
    return roots


def vector_control_path(pgroot: Path) -> Path:
    return pgroot / "share" / "extension" / "vector.control"


def vector_files_installed(pgroot: Path) -> bool:
    return vector_control_path(pgroot).is_file()


def detect_postgres_major(engine: Engine) -> int | None:
    """Read server major version from a live connection."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SHOW server_version")).fetchone()
        if not row or not row[0]:
            return None
        match = re.match(r"^(\d+)", str(row[0]))
        return int(match.group(1)) if match else None
    except Exception:
        return None


def guess_pgroot_for_major(major: int) -> Path | None:
    for ver, root in postgres_install_roots():
        if ver == major:
            return root
    return Path(rf"C:\Program Files\PostgreSQL\{major}")


def resolve_source_dir(source: str | Path) -> tuple[Path | None, tempfile.TemporaryDirectory[str] | None, str | None]:
    """Return a directory containing pgvector artifacts; extract zip when needed."""
    path = Path(source).expanduser().resolve()
    if not path.exists():
        return None, None, f"Path not found: {path}"

    if path.is_file() and path.suffix.lower() == ".zip":
        tmp = tempfile.TemporaryDirectory(prefix="sylo-pgvector-")
        with zipfile.ZipFile(path) as zf:
            zf.extractall(tmp.name)
        return Path(tmp.name), tmp, None

    if path.is_dir():
        return path, None, None

    return None, None, f"Select a pgvector folder or .zip file: {path}"


def _collect_pgvector_files(source_dir: Path) -> tuple[list[Path], list[Path], str | None]:
    dlls: list[Path] = []
    ext_files: list[Path] = []
    for file in source_dir.rglob("*"):
        if not file.is_file():
            continue
        name = file.name.lower()
        if name.endswith(".dll"):
            dlls.append(file)
        elif name == "vector.control" or (name.startswith("vector--") and name.endswith(".sql")):
            ext_files.append(file)
    if not ext_files:
        return [], [], "No vector.control or vector--*.sql found in the selected folder."
    return dlls, ext_files, None


def install_pgvector_files(source_dir: Path, pgroot: Path) -> dict[str, Any]:
    """Copy pgvector binaries/extension SQL into a PostgreSQL install root."""
    dlls, ext_files, err = _collect_pgvector_files(source_dir)
    if err:
        return {"ok": False, "error": err}

    lib_dir = pgroot / "lib"
    ext_dir = pgroot / "share" / "extension"
    copied: list[str] = []

    try:
        lib_dir.mkdir(parents=True, exist_ok=True)
        ext_dir.mkdir(parents=True, exist_ok=True)
        for dll in dlls:
            dest = lib_dir / dll.name
            shutil.copy2(dll, dest)
            copied.append(str(dest))
        for ext in ext_files:
            dest = ext_dir / ext.name
            shutil.copy2(ext, dest)
            copied.append(str(dest))
    except PermissionError as exc:
        return {
            "ok": False,
            "error": f"Permission denied copying into {pgroot}. Approve the admin prompt or run Sylo as administrator.",
            "needs_elevation": True,
            "pgroot": str(pgroot),
            "source_dir": str(source_dir),
        }
    except OSError as exc:
        return {"ok": False, "error": str(exc), "pgroot": str(pgroot)}

    if not vector_files_installed(pgroot):
        return {
            "ok": False,
            "error": f"Copy finished but {vector_control_path(pgroot)} is still missing.",
            "copied": copied,
            "pgroot": str(pgroot),
        }

    return {
        "ok": True,
        "copied": copied,
        "pgroot": str(pgroot),
        "vector_control_path": str(vector_control_path(pgroot)),
    }


def windows_install_status(postgres_major: int | None) -> dict[str, Any]:
    """Whether pgvector files appear on disk for the detected major version."""
    major = postgres_major
    pgroot = guess_pgroot_for_major(major) if major else None
    files_ok = bool(pgroot and vector_files_installed(pgroot))
    return {
        "postgres_major": major,
        "pgroot": str(pgroot) if pgroot else None,
        "vector_files_installed": files_ok,
        "vector_control_path": str(vector_control_path(pgroot)) if pgroot else None,
        "prebuilt_releases_page": PREBUILT_RELEASES_PAGE,
    }


def guided_pgvector_download_step(postgres_major: int | None) -> str:
    major = postgres_major if postgres_major else "your Postgres major version"
    return (
        f"Optional — semantic search: download pgvector for PostgreSQL {major} from "
        f"{PREBUILT_RELEASES_PAGE}, extract the zip, then use Browse below."
    )


def layman_pgvector_steps(
    postgres_major: int | None,
    *,
    files_installed: bool,
    db_mode: str = "local",
) -> list[str]:
    """Plain-language steps for optional semantic search."""
    if db_mode == "remote":
        return [
            "Optional semantic search needs pgvector installed on the shared Postgres server (not this PC).",
            guided_pgvector_download_step(postgres_major).replace("Browse below", "have your server admin install the files"),
            "Then click Enable semantic search here (superuser password, not saved).",
            "Test connection — pgvector should show enabled.",
        ]

    if files_installed:
        return [
            "pgvector files are on this PC.",
            "Click Enable semantic search (superuser password above — not saved).",
            "Test connection — pgvector should show enabled.",
        ]

    return [
        "Optional: keyword search already works without pgvector.",
        guided_pgvector_download_step(postgres_major),
        "FieldBrain Settings → Browse → pick the extracted folder (or the .zip).",
        "Click Install pgvector & enable semantic search (superuser password, not saved).",
        "Test connection again.",
    ]
