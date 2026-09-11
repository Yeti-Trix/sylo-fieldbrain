"""Hybrid search: keyword tsvector + optional pgvector cosine via simplified RRF."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from _db_lib import check_pgvector, ollama_base_url
from models import GlobalSettings
from services.embedding_service import generate_single_embedding
from services.global_brain_support import get_global_brain_shell_project_id

logger = logging.getLogger(__name__)

KEYWORD_WEIGHT = 0.7
SEMANTIC_WEIGHT = 0.3
RRF_K = 60
SNIPPET_CHARS = 300
SOURCE_DOCUMENT = "document"
SOURCE_BRAIN = "brain"


@dataclass
class SearchHit:
    id: int
    project_id: int
    source_type: str
    source_id: str | None
    label: str
    path: str
    content: str
    chunk_index: int = 0


def _get_embedding_model(session: Session) -> str | None:
    settings = session.query(GlobalSettings).filter(GlobalSettings.id == 1).first()
    if settings and settings.embedding_model and settings.embedding_model.strip():
        return settings.embedding_model.strip()
    return "nomic-embed-text"


def _keyword_search(
    session: Session,
    project_ids: list[int],
    q: str,
    limit: int,
    *,
    source_type: str | None = None,
) -> list[SearchHit]:
    filter_sql = ""
    params: dict[str, Any] = {"pids": project_ids, "q": q.strip(), "lim": limit}
    if source_type and source_type.strip():
        filter_sql = " AND source_type = :stype"
        params["stype"] = source_type.strip()

    rows = session.execute(
        text(
            f"""
            SELECT id, project_id, source_type, source_id, label, path, content, chunk_index
            FROM search_index
            WHERE project_id = ANY(:pids)
              AND search_vector @@ plainto_tsquery('english', :q)
              {filter_sql}
            ORDER BY ts_rank_cd(
                '{{0.1, 0.2, 0.4, 1.0}}'::float4[],
                search_vector,
                plainto_tsquery('english', :q)
            ) DESC
            LIMIT :lim
            """
        ),
        params,
    ).fetchall()

    return [
        SearchHit(
            id=row[0],
            project_id=int(row[1]),
            source_type=row[2],
            source_id=row[3],
            label=row[4] or "",
            path=row[5] or "",
            content=row[6] or "",
            chunk_index=int(row[7] or 0),
        )
        for row in rows
    ]


def _semantic_search(
    session: Session,
    project_ids: list[int],
    embedding: list[float],
    limit: int,
    *,
    source_type: str | None = None,
) -> list[SearchHit]:
    emb_str = "[" + ",".join(str(v) for v in embedding) + "]"
    filter_sql = ""
    params: dict[str, Any] = {"pids": project_ids, "emb": emb_str, "lim": limit}
    if source_type and source_type.strip():
        filter_sql = " AND source_type = :stype"
        params["stype"] = source_type.strip()

    try:
        rows = session.execute(
            text(
                f"""
                SELECT id, project_id, source_type, source_id, label, path, content, chunk_index
                FROM search_index
                WHERE project_id = ANY(:pids)
                  AND embedding IS NOT NULL
                  {filter_sql}
                ORDER BY embedding <=> CAST(:emb AS vector)
                LIMIT :lim
                """
            ),
            params,
        ).fetchall()
    except Exception as exc:
        err = str(exc).lower()
        if "embedding" in err and "does not exist" in err:
            logger.warning("Semantic search skipped: no embedding column (%s)", exc)
        else:
            logger.warning("Semantic search failed: %s", exc)
        session.rollback()
        return []

    return [
        SearchHit(
            id=row[0],
            project_id=int(row[1]),
            source_type=row[2],
            source_id=row[3],
            label=row[4] or "",
            path=row[5] or "",
            content=row[6] or "",
            chunk_index=int(row[7] or 0),
        )
        for row in rows
    ]


def _snippet(content: str, max_chars: int = SNIPPET_CHARS) -> str:
    c = (content or "").strip()
    if len(c) <= max_chars:
        return c
    return c[:max_chars].strip()


def _fuse_rrf(
    keyword_hits: list[SearchHit],
    semantic_hits: list[SearchHit],
) -> list[tuple[SearchHit, float]]:
    kw_rank = {h.id: i for i, h in enumerate(keyword_hits)}
    sem_rank = {h.id: i for i, h in enumerate(semantic_hits)}
    all_ids = set(kw_rank) | set(sem_rank)

    hit_by_id: dict[int, SearchHit] = {}
    for h in keyword_hits:
        hit_by_id[h.id] = h
    for h in semantic_hits:
        hit_by_id.setdefault(h.id, h)

    max_possible = KEYWORD_WEIGHT / (RRF_K + 1) + SEMANTIC_WEIGHT / (RRF_K + 1)
    scored: list[tuple[SearchHit, float]] = []
    for doc_id in all_ids:
        rrf = 0.0
        if doc_id in kw_rank:
            rrf += KEYWORD_WEIGHT / (RRF_K + kw_rank[doc_id] + 1)
        if doc_id in sem_rank:
            rrf += SEMANTIC_WEIGHT / (RRF_K + sem_rank[doc_id] + 1)
        normalized = min(rrf / max_possible, 1.0) if max_possible > 0 else 0.0
        scored.append((hit_by_id[doc_id], normalized))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _hit_to_dict(hit: SearchHit, score: float, *, global_pid: int | None = None) -> dict[str, Any]:
    is_global = global_pid is not None and hit.project_id == global_pid
    return {
        "id": hit.id,
        "project_id": None if is_global else hit.project_id,
        "scope": "global" if is_global else "project",
        "type": hit.source_type,
        "source_id": hit.source_id,
        "label": hit.label,
        "path": hit.path,
        "snippet": _snippet(hit.content),
        "chunk_index": hit.chunk_index,
        "score": round(score, 4),
    }


def hybrid_search(
    session: Session,
    project_id: int | None,
    query: str,
    *,
    limit: int = 25,
    source_type: str | None = None,
    use_semantic: bool | None = None,
) -> list[dict[str, Any]]:
    """Hybrid search with asymmetric scope visibility.

    project_id given: that project's rows PLUS curated global rows (brain + library).
    project_id None: global rows only — project-local knowledge stays invisible
    shop-wide until promoted.
    Keyword-only when pgvector/Ollama unavailable.
    """
    q = (query or "").strip()
    if not q:
        return []

    global_pid = get_global_brain_shell_project_id(session)
    if project_id is None:
        project_ids = [global_pid]
    else:
        project_ids = [int(project_id)]
        if global_pid not in project_ids:
            project_ids.append(global_pid)

    cap = max(1, min(int(limit), 50))
    fetch_lim = max(cap, 50)

    keyword_hits = _keyword_search(session, project_ids, q, fetch_lim, source_type=source_type)

    semantic_hits: list[SearchHit] = []
    pg_ok, _ = check_pgvector()
    if use_semantic is not False and pg_ok:
        emb_model = _get_embedding_model(session)
        query_emb = generate_single_embedding(q, ollama_base_url(), emb_model)
        if query_emb:
            semantic_hits = _semantic_search(
                session, project_ids, query_emb, fetch_lim, source_type=source_type
            )

    if not semantic_hits:
        return [
            _hit_to_dict(h, 1.0 - (i * 0.01), global_pid=global_pid)
            for i, h in enumerate(keyword_hits[:cap])
        ]

    fused = _fuse_rrf(keyword_hits, semantic_hits)
    return [_hit_to_dict(hit, score, global_pid=global_pid) for hit, score in fused[:cap]]
