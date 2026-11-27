"""Unit tests for app/chunking.py: sentence splitting and overlapping chunks."""

import pytest

from app.chunking import chunk_embedding_text, chunk_text, split_sentences


def test_split_sentences_on_punctuation_and_paragraphs():
    text = "First one. Second one! Third one?\n\nNew paragraph"
    assert split_sentences(text) == [
        "First one.",
        "Second one!",
        "Third one?",
        "New paragraph",
    ]


def test_short_text_is_one_chunk():
    chunks = chunk_text("One two three. Four five six.", max_words=10, overlap_words=3)
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].word_count == 6


def test_next_chunk_repeats_sentences_that_fit_the_overlap_exactly():
    # Each sentence has 3 words. A chunk holds 6 words; the overlap is exactly 3 words,
    # so the last sentence of each chunk must start the next chunk.
    text = "Aa bb cc. Dd ee ff. Gg hh ii."
    chunks = chunk_text(text, max_words=6, overlap_words=3)
    assert [chunk.text for chunk in chunks] == [
        "Aa bb cc. Dd ee ff.",
        "Dd ee ff. Gg hh ii.",
    ]


def test_chunk_indexes_count_up_from_zero():
    text = " ".join(f"Sentence number {n} here." for n in range(10))
    chunks = chunk_text(text, max_words=8, overlap_words=2)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


def test_overlap_must_be_smaller_than_max_words():
    with pytest.raises(ValueError):
        chunk_text("Some text.", max_words=5, overlap_words=5)


def test_embedding_text_puts_title_first():
    assert chunk_embedding_text("Returns", "Body text.") == "Returns\n\nBody text."