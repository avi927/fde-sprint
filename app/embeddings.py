"""Embedding model wrapper: the single place where text becomes vectors."""

import logging
from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingDimensionError(Exception):
    """Raised when the model's vectors don't match the configured dimensions."""


@lru_cache
def _get_model() -> TextEmbedding:
    """Load the embedding model once per process (loading takes about a second)."""
    settings = get_settings()
    settings.embedding_cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "embedding_model_loading",
        extra={"extra_fields": {"model": settings.embedding_model}},
    )
    return TextEmbedding(
        model_name=settings.embedding_model,
        cache_dir=str(settings.embedding_cache_dir),
    )


def _check_dimensions(vector: np.ndarray) -> np.ndarray:
    """Fail fast if a vector doesn't match the configured size (and the DB column)."""
    expected = get_settings().embedding_dimensions
    if len(vector) != expected:
        raise EmbeddingDimensionError(
            f"Model returned {len(vector)} dimensions, expected {expected}"
        )
    return vector


def embed_passages(texts: list[str]) -> list[np.ndarray]:
    """Embed documents for storage. All texts are embedded in one batch for speed."""
    return [_check_dimensions(vector) for vector in _get_model().embed(texts)]


def embed_query(text: str) -> np.ndarray:
    """Embed a search query, with the model's retrieval instruction in front."""
    settings = get_settings()
    vectors = _get_model().embed([settings.embedding_query_prefix + text])
    return _check_dimensions(next(iter(vectors)))