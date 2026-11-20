"""Cross-encoder reranking: score (question, passage) pairs with a precise model."""

import logging
from functools import lru_cache

from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _get_reranker() -> TextCrossEncoder:
    """Load the cross-encoder once per process."""
    settings = get_settings()
    settings.embedding_cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "reranker_model_loading",
        extra={"extra_fields": {"model": settings.reranker_model}},
    )
    return TextCrossEncoder(
        model_name=settings.reranker_model,
        cache_dir=str(settings.embedding_cache_dir),
    )


def score_pairs(query: str, passages: list[str]) -> list[float]:
    """Relevance score for each passage, in the same order. Higher = more relevant."""
    if not passages:
        return []
    return [float(score) for score in _get_reranker().rerank(query, passages)]


def warm_up_reranker() -> None:
    """Load the reranker now, so the first real request doesn't pay the loading time."""
    _get_reranker()