"""Unit tests for Reciprocal Rank Fusion in app/search.py (no database needed)."""

import pytest

from app.search import ChunkHit, reciprocal_rank_fusion


def make_hit(chunk_id: int, slug: str = "doc", chunk_index: int = 0) -> ChunkHit:
    return ChunkHit(
        chunk_id=chunk_id,
        slug=slug,
        title="Title",
        category="general",
        chunk_index=chunk_index,
        content="Some content.",
        score=0.0,
    )


def test_single_list_scores_are_one_over_k_plus_rank():
    fused = reciprocal_rank_fusion([[make_hit(1), make_hit(2)]], k=60)
    assert [hit.chunk_id for hit in fused] == [1, 2]
    assert fused[0].score == pytest.approx(1 / 61, abs=1e-6)
    assert fused[1].score == pytest.approx(1 / 62, abs=1e-6)


def test_hit_found_by_both_lists_ranks_first():
    semantic = [make_hit(1), make_hit(2), make_hit(3)]
    keyword = [make_hit(3), make_hit(4)]
    fused = reciprocal_rank_fusion([semantic, keyword], k=60)
    assert fused[0].chunk_id == 3
    assert fused[0].score == pytest.approx(1 / 63 + 1 / 61, abs=1e-6)


def test_each_chunk_appears_once():
    semantic = [make_hit(1), make_hit(2)]
    keyword = [make_hit(2), make_hit(1)]
    fused = reciprocal_rank_fusion([semantic, keyword], k=60)
    assert sorted(hit.chunk_id for hit in fused) == [1, 2]


def test_source_id_is_slug_hash_index():
    assert make_hit(7, slug="returns-guide", chunk_index=2).source_id == "returns-guide#2"