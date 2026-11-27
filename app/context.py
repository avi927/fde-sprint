"""Context engineering: turn retrieved chunks into a clean, labelled, size-limited context."""

import re
from dataclasses import dataclass

from app.chunking import split_sentences
from app.search import ChunkHit

# Tags that could fake our prompt structure if they appeared inside document text.
_STRUCTURE_TAGS = re.compile(r"</?\s*(source|context|question)\b[^>]*>")


@dataclass(frozen=True)
class ContextBundle:
    """The context text for the prompt, plus which chunks made it in and why others didn't."""

    text: str
    hits: list[ChunkHit]
    dropped_duplicates: int
    dropped_budget: int

    @property
    def source_ids(self) -> list[str]:
        """IDs the model is allowed to cite."""
        return [hit.source_id for hit in self.hits]


def sanitize(text: str) -> str:
    """Remove structure tags so untrusted text can't break out of its <source> block."""
    return _STRUCTURE_TAGS.sub("", text)


def _overlap_ratio(content: str, seen_sentences: set[str]) -> float:
    """Share of this chunk's sentences that are already in the context (0.0 to 1.0)."""
    sentences = split_sentences(content)
    if not sentences:
        return 1.0
    repeated = sum(1 for sentence in sentences if sentence in seen_sentences)
    return repeated / len(sentences)


def build_context(
    hits: list[ChunkHit], max_words: int = 700, max_overlap: float = 0.6
) -> ContextBundle:
    """Keep hits in relevance order; skip near-duplicates; stop at the word budget; label each."""
    selected: list[ChunkHit] = []
    seen_sentences: set[str] = set()
    used_words = 0
    dropped_duplicates = 0
    dropped_budget = 0

    for hit in hits:
        if _overlap_ratio(hit.content, seen_sentences) > max_overlap:
            dropped_duplicates += 1
            continue

        words = len(hit.content.split())
        if selected and used_words + words >= max_words:
            dropped_budget += 1
            continue

        selected.append(hit)
        seen_sentences.update(split_sentences(hit.content))
        used_words += words

    blocks = [
        f'<source id="{hit.source_id}" title="{sanitize(hit.title).replace(chr(34), chr(39))}">\n'
        f"{sanitize(hit.content)}\n"
        f"</source>"
        for hit in selected
    ]
    text = "<context>\n" + "\n\n".join(blocks) + "\n</context>"
    return ContextBundle(
        text=text,
        hits=selected,
        dropped_duplicates=dropped_duplicates,
        dropped_budget=dropped_budget,
    )