"""Split long documents into overlapping, sentence-aligned chunks."""

import re
from dataclasses import dataclass

# A sentence ends with . ! or ? followed by whitespace.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    """One piece of a document."""

    index: int
    text: str
    word_count: int


def split_sentences(text: str) -> list[str]:
    """Split text into sentences; paragraph breaks (blank lines) are always boundaries."""
    sentences: list[str] = []
    for paragraph in text.split("\n\n"):
        for sentence in _SENTENCE_BOUNDARY.split(paragraph.strip()):
            if sentence.strip():
                sentences.append(sentence.strip())
    return sentences


def chunk_text(text: str, max_words: int = 120, overlap_words: int = 30) -> list[Chunk]:
    """Pack whole sentences into chunks of up to max_words, repeating ~overlap_words.

    A single sentence longer than max_words becomes its own (oversized) chunk.
    """
    if overlap_words >= max_words:
        raise ValueError("overlap_words must be smaller than max_words")

    chunks: list[Chunk] = []
    current: list[str] = []
    current_words = 0

    for sentence in split_sentences(text):
        sentence_words = len(sentence.split())

        # Adding this sentence would overflow the chunk: close it and start a new one.
        if current and current_words + sentence_words > max_words:
            chunks.append(_make_chunk(len(chunks), current))
            current = _overlap_tail(current, overlap_words)
            current_words = sum(len(s.split()) for s in current)

        current.append(sentence)
        current_words += sentence_words

    if current:
        chunks.append(_make_chunk(len(chunks), current))
    return chunks


def _overlap_tail(sentences: list[str], overlap_words: int) -> list[str]:
    """The last sentences (up to overlap_words in total) to repeat in the next chunk."""
    tail: list[str] = []
    words = 0
    for sentence in reversed(sentences):
        sentence_words = len(sentence.split())
        if words + sentence_words > overlap_words:
            break
        tail.insert(0, sentence)
        words += sentence_words
    return tail


def _make_chunk(index: int, sentences: list[str]) -> Chunk:
    """Join sentences into one chunk."""
    text = " ".join(sentences)
    return Chunk(index=index, text=text, word_count=len(text.split()))