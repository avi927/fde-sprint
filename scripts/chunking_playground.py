"""See how chunk size and overlap change the way long documents are split."""

import json
from pathlib import Path

from app.chunking import chunk_text

ROOT = Path(__file__).resolve().parent.parent
KB_FILE = ROOT / "data" / "knowledge_base.json"

CONFIGS = [
    {"name": "small", "max_words": 60, "overlap_words": 15},
    {"name": "large", "max_words": 150, "overlap_words": 30},
    {"name": "small_no_overlap", "max_words": 60, "overlap_words": 0},
]

FACTS_TO_TRACK = ["restocking fee", "unless they are faulty", "31 January"]


def main() -> None:
    docs = json.loads(KB_FILE.read_text(encoding="utf-8"))
    returns_guide = next(doc for doc in docs if doc["slug"] == "returns-guide")
    print(f"Document: {returns_guide['title']} ({len(returns_guide['content'].split())} words)\n")

    for config in CONFIGS:
        chunks = chunk_text(
            returns_guide["content"],
            max_words=config["max_words"],
            overlap_words=config["overlap_words"],
        )
        print(
            f"=== {config['name']}: max_words={config['max_words']}, "
            f"overlap_words={config['overlap_words']} -> {len(chunks)} chunks ==="
        )
        for chunk in chunks:
            preview = chunk.text[:70].replace("\n", " ")
            print(f"  #{chunk.index} ({chunk.word_count:>3} words) {preview}...")

        print("  Where are the key facts?")
        for fact in FACTS_TO_TRACK:
            found_in = [chunk.index for chunk in chunks if fact in chunk.text]
            print(f"    {fact!r:<26} -> chunks {found_in}")

        total = sum(
            len(chunk_text(doc["content"], config["max_words"], config["overlap_words"]))
            for doc in docs
        )
        print(f"  Whole knowledge base: {len(docs)} documents -> {total} chunks\n")


if __name__ == "__main__":
    main()