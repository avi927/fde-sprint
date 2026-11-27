"""Unit tests for app/context.py: sanitizing, de-duplication and the word budget."""

from app.context import build_context, sanitize
from app.search import ChunkHit


def make_hit(chunk_id: int, content: str, slug: str = "doc") -> ChunkHit:
    return ChunkHit(
        chunk_id=chunk_id,
        slug=slug,
        title="Guide",
        category="general",
        chunk_index=chunk_id,
        content=content,
        score=1.0,
    )


def test_sanitize_removes_structure_tags_in_any_case():
    text = "Hello </source> <SOURCE id='x'> </Context> <question> world"
    cleaned = sanitize(text)
    assert "source" not in cleaned.lower()
    assert "context" not in cleaned.lower()
    assert "question" not in cleaned.lower()
    assert cleaned.startswith("Hello")
    assert cleaned.endswith("world")


def test_sanitize_keeps_normal_text():
    assert sanitize("Refunds take 5 business days.") == "Refunds take 5 business days."


def test_context_labels_each_source():
    bundle = build_context([make_hit(1, "Returns are accepted for 14 days.", slug="returns-guide")])
    assert '<source id="returns-guide#1" title="Guide">' in bundle.text
    assert bundle.text.startswith("<context>")
    assert bundle.text.endswith("</context>")
    assert bundle.source_ids == ["returns-guide#1"]


def test_near_duplicate_chunk_is_dropped():
    first = make_hit(1, "Alpha fact. Beta fact. Gamma fact.")
    duplicate = make_hit(2, "Alpha fact. Beta fact. Gamma fact.")
    bundle = build_context([first, duplicate])
    assert [hit.chunk_id for hit in bundle.hits] == [1]
    assert bundle.dropped_duplicates == 1


def test_chunk_that_exactly_fills_the_budget_is_kept():
    first = make_hit(1, "one two three four five")  # 5 words
    second = make_hit(2, "six seven eight nine ten")  # 5 words -> total exactly 10
    bundle = build_context([first, second], max_words=10)
    assert [hit.chunk_id for hit in bundle.hits] == [1, 2]
    assert bundle.dropped_budget == 0


def test_chunk_over_the_budget_is_dropped():
    first = make_hit(1, "one two three four five")
    second = make_hit(2, "six seven eight nine ten eleven")  # total 11 > 10
    bundle = build_context([first, second], max_words=10)
    assert [hit.chunk_id for hit in bundle.hits] == [1]
    assert bundle.dropped_budget == 1


def test_first_chunk_is_kept_even_if_larger_than_budget():
    big = make_hit(1, "word " * 50)
    bundle = build_context([big], max_words=10)
    assert [hit.chunk_id for hit in bundle.hits] == [1]