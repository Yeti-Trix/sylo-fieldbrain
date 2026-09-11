"""Catalog metadata for library documents (agent-read summary, not full-file ingest)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from models import Document, DocumentAnalysis, DocumentPdfOutline
from services.document_formats import normalize_category
from services.document_ingest import _index_project_id_for_document, index_document_text
from services.document_service import document_to_dict


def _parse_tags(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    text = raw.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(t).strip() for t in parsed if str(t).strip()]
        except json.JSONDecodeError:
            pass
    return [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]


def _normalize_outline(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not entries:
        return []
    out: list[dict[str, Any]] = []
    for i, row in enumerate(entries):
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        level = int(row.get("level") or 1)
        page = row.get("page")
        if page is None:
            page = row.get("physical_pdf_page")
        physical_page = int(page) if page is not None and str(page).isdigit() else 0
        out.append(
            {
                "level": max(1, level),
                "title": title,
                "physical_pdf_page": physical_page,
                "toc_page_claimed": row.get("toc_page_claimed"),
                "verification": str(row.get("verification") or "agent"),
                "sequence": int(row.get("sequence") if row.get("sequence") is not None else i),
            }
        )
    return out


def _build_index_text(
    document: Document,
    description: str,
    tags: list[str],
    outline: list[dict[str, Any]],
) -> str:
    parts = [
        f"Title: {document.title}",
        f"Filename: {document.original_filename}",
        f"Category: {document.category}",
    ]
    if document.manufacturer:
        parts.append(f"Manufacturer: {document.manufacturer}")
    if document.model:
        parts.append(f"Model: {document.model}")
    if document.version:
        parts.append(f"Version: {document.version}")
    if tags:
        parts.append(f"Tags: {', '.join(tags)}")
    parts.append("")
    parts.append(description.strip())
    if outline:
        parts.append("")
        parts.append("Outline:")
        for row in outline:
            indent = "  " * (max(1, row["level"]) - 1)
            page_note = f" (p.{row['physical_pdf_page'] + 1})" if row["physical_pdf_page"] else ""
            parts.append(f"{indent}- {row['title']}{page_note}")
    return "\n".join(parts).strip()


def catalog_document(
    session: Session,
    document_id: int,
    *,
    description: str,
    tags: str | list[str] | None = None,
    category: str | None = None,
    title: str | None = None,
    manufacturer: str | None = None,
    model: str | None = None,
    version: str | None = None,
    outline: list[dict[str, Any]] | None = None,
    project_id: int | None = None,
    embed: bool = True,
) -> dict[str, Any]:
    """Write catalog rows and index summary text for search (not full-file extraction)."""
    desc = (description or "").strip()
    if not desc:
        raise ValueError("description is required — agent must summarize after reading the file.")

    document = (
        session.query(Document)
        .filter(Document.id == document_id, Document.archived.is_(False))
        .first()
    )
    if not document:
        raise ValueError("Document not found")

    tag_list = _parse_tags(tags)
    outline_rows = _normalize_outline(outline)

    if title and title.strip():
        document.title = title.strip()[:255]
    if category:
        document.category = normalize_category(category)
    if manufacturer is not None:
        document.manufacturer = manufacturer.strip()[:100] or None
    if model is not None:
        document.model = model.strip()[:100] or None
    if version is not None:
        document.version = version.strip()[:50] or None
    if tag_list:
        document.tags_json = json.dumps(tag_list)

    analysis = (
        session.query(DocumentAnalysis)
        .filter(DocumentAnalysis.document_id == document.id)
        .first()
    )
    if analysis:
        analysis.llm_index_description = desc
    else:
        session.add(
            DocumentAnalysis(
                document_id=document.id,
                llm_index_description=desc,
            )
        )

    session.query(DocumentPdfOutline).filter(DocumentPdfOutline.document_id == document.id).delete()
    for row in outline_rows:
        session.add(
            DocumentPdfOutline(
                document_id=document.id,
                level=row["level"],
                title=row["title"],
                toc_page_claimed=row.get("toc_page_claimed"),
                physical_pdf_page=row["physical_pdf_page"],
                verification=row["verification"],
                sequence=row["sequence"],
            )
        )

    session.flush()
    index_pid = _index_project_id_for_document(session, document, project_id)
    index_text = _build_index_text(document, desc, tag_list, outline_rows)
    index_stats = index_document_text(
        session,
        document,
        index_text,
        index_project_id=index_pid,
    )

    return {
        "document": document_to_dict(document),
        "catalog": {
            "description_chars": len(desc),
            "tags": tag_list,
            "outline_entries": len(outline_rows),
            "indexed_for_search": True,
            "embeddings_written": index_stats.get("embeddings_written", 0) if embed else 0,
        },
        **index_stats,
    }
