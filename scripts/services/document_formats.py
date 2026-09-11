"""Supported library file types and which Sylo skill reads them (agent-side)."""

from __future__ import annotations

# Extensions FieldBrain stores in the global/project document library (bytes in Postgres).
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".txt",
        ".md",
        ".markdown",
        ".docx",
        ".xlsx",
        ".xlsm",
        ".ods",
        ".csv",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".bmp",
    }
)

MAX_FILE_SIZE = 50 * 1024 * 1024

DOCUMENT_CATEGORIES: frozenset[str] = frozenset(
    {
        "manual",
        "datasheet",
        "requirements",
        "email",
        "howto",
        "guide",
        "schematic",
        "spreadsheet",
        "image",
        "markdown",
        "reference",
        "other",
    }
)

MIME_BY_EXT: dict[str, str] = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".csv": "text/csv",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}

# Agent reads the file with these Sylo capabilities before calling fieldbrain_document_catalog.
READER_HINTS: dict[str, str] = {
    ".pdf": "sylo-pdf-reader: search_schematic_pdf (and region tools as needed)",
    ".xlsx": "sylo-spreadsheet: read_spreadsheet",
    ".xlsm": "sylo-spreadsheet: read_spreadsheet (formulas optional)",
    ".ods": "sylo-spreadsheet: read_spreadsheet",
    ".csv": "Pi read tool (plain text)",
    ".txt": "Pi read tool",
    ".md": "Pi read tool",
    ".markdown": "Pi read tool",
    ".docx": "Chat attachment + agent summary (extract headings/topics); template-docx-writer for embedded images only",
    ".jpg": "Vision on attachment — describe what the image shows",
    ".jpeg": "Vision on attachment — describe what the image shows",
    ".png": "Vision on attachment — describe what the image shows",
    ".webp": "Vision on attachment — describe what the image shows",
    ".gif": "Vision on attachment — describe what the image shows",
    ".bmp": "Vision on attachment — describe what the image shows",
}

IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"})


def mime_for_ext(ext: str) -> str | None:
    return MIME_BY_EXT.get(ext.lower())


def reader_hint_for_ext(ext: str) -> str | None:
    return READER_HINTS.get(ext.lower())


def normalize_category(raw: str | None) -> str:
    cat = (raw or "other").strip().lower().replace("-", "").replace("_", "")
    aliases = {
        "howto": "howto",
        "howtoguide": "howto",
        "howguide": "howto",
        "spec": "requirements",
        "req": "requirements",
        "datasheets": "datasheet",
        "manuals": "manual",
        "photo": "image",
        "picture": "image",
        "img": "image",
        "emailchain": "email",
        "mail": "email",
    }
    cat = aliases.get(cat, cat)
    if cat in DOCUMENT_CATEGORIES:
        return cat
    return "other"


def is_image_ext(ext: str) -> bool:
    return ext.lower() in IMAGE_EXTENSIONS
