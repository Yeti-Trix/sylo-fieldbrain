"""Brain filesystem path helpers (stub — full write/index in later phases)."""

from __future__ import annotations

from pathlib import Path

from _db_lib import package_root

GLOBAL_BRAIN_PROJECT_NAME = "__fieldbrain_global_brain__"

_BRAIN_SUBDIRS = (
    "inbox",
    "issues",
    "gotchas",
    "runbooks",
    "decisions",
    "common_issues",
    "attachments",
)


def storage_root() -> Path:
    """Shared on-disk storage under the package (server-side or local Postgres host)."""
    root = package_root() / "shared" / "storage"
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_brain_root(project_id: int) -> Path:
    return storage_root() / str(project_id) / "brain"


def global_brain_root() -> Path:
    return storage_root() / "global" / "brain"


def ensure_project_brain_layout(project_id: int) -> Path:
    """Create brain/ subdirs if missing. Does not seed INDEX.md yet (Phase 4+)."""
    root = project_brain_root(project_id)
    root.mkdir(parents=True, exist_ok=True)
    for sub in _BRAIN_SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def ensure_global_brain_layout() -> Path:
    root = global_brain_root()
    root.mkdir(parents=True, exist_ok=True)
    for sub in (*_BRAIN_SUBDIRS, "references"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def safe_relative_brain_path(spec: str) -> str | None:
    if not spec or not spec.strip():
        return None
    raw = spec.strip().strip("`").replace("\\", "/")
    parts = Path(raw).parts
    if any(p == ".." or p.startswith("..") for p in parts):
        return None
    if parts and parts[0] == "brain":
        parts = parts[1:]
    if not parts:
        return None
    rel = "/".join(parts)
    if ".." in rel.split("/"):
        return None
    if not rel.endswith(".md"):
        return None
    return rel


def resolve_brain_path(brain_root: Path, relative: str) -> Path | None:
    rel = safe_relative_brain_path(relative)
    if not rel:
        return None
    target = (brain_root / rel).resolve()
    root_resolved = brain_root.resolve()
    if root_resolved not in target.parents and target != root_resolved:
        return None
    return target
