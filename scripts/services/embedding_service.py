"""Sync Ollama embedding service for search index vectors."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from _db_lib import ollama_base_url

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768
BATCH_SIZE = 64
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"


def _normalize_endpoint(endpoint: str) -> str:
    return endpoint.rstrip("/").replace("/v1", "")


def generate_embeddings(
    texts: list[str],
    endpoint: str | None = None,
    model: str | None = None,
    batch_size: int = BATCH_SIZE,
) -> list[list[float] | None]:
    """Generate embeddings for texts via Ollama /api/embed (sync).

    Returns a list parallel to *texts*; each element is a vector or None on failure.
    """
    if not texts:
        return []

    base = _normalize_endpoint(endpoint or ollama_base_url())
    embed_model = (model or DEFAULT_EMBEDDING_MODEL).strip() or DEFAULT_EMBEDDING_MODEL
    results: list[list[float] | None] = [None] * len(texts)

    with httpx.Client(timeout=120.0) as client:
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            try:
                resp = client.post(
                    f"{base}/api/embed",
                    json={"model": embed_model, "input": batch},
                )
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                embeddings = data.get("embeddings") or []
                for i, emb in enumerate(embeddings):
                    if i < len(batch) and emb:
                        results[start + i] = emb
            except Exception as exc:
                logger.error(
                    "Embedding batch failed offset=%d size=%d: %s",
                    start,
                    len(batch),
                    exc,
                )

    return results


def generate_single_embedding(
    text: str,
    endpoint: str | None = None,
    model: str | None = None,
) -> list[float] | None:
    """Generate one embedding vector; None on failure."""
    results = generate_embeddings([text], endpoint=endpoint, model=model, batch_size=1)
    return results[0] if results else None
