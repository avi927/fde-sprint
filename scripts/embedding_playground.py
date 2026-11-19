"""Hands-on with embeddings: turn sentences into vectors and measure how similar they are."""

import time

import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"

QUERY = "How do I get my money back?"

DOCUMENTS = [
    "What is your refund policy?",
    "Returns are accepted within 14 days of delivery.",
    "My package hasn't arrived yet.",
    "How do I reset my password?",
    "The cat sat on the mat.",
    "I do not want a refund.",
]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Angle-based similarity: 1.0 = same direction (same meaning), 0 = unrelated."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main() -> None:
    print(f"Loading {MODEL_NAME} (first run downloads the model)...")
    start = time.perf_counter()
    model = TextEmbedding(model_name=MODEL_NAME)
    print(f"Loaded in {time.perf_counter() - start:.1f} s\n")

    # 1. What does an embedding look like?
    query_vector = next(iter(model.embed([QUERY])))
    print(f"Query: {QUERY!r}")
    print(f"Dimensions: {len(query_vector)}")
    print(f"First 5 numbers: {np.round(query_vector[:5], 4)}")
    print(f"Vector length (norm): {np.linalg.norm(query_vector):.4f}\n")

    # 2. Embed all documents at once (batching is faster than one by one)
    start = time.perf_counter()
    doc_vectors = list(model.embed(DOCUMENTS))
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"Embedded {len(DOCUMENTS)} documents in {elapsed_ms:.0f} ms\n")

    # 3. Rank documents by similarity to the query (a tiny semantic search)
    scored = []
    for text, vector in zip(DOCUMENTS, doc_vectors):
        cosine = cosine_similarity(query_vector, vector)
        dot = float(np.dot(query_vector, vector))
        scored.append((cosine, dot, text))
    scored.sort(reverse=True)

    print(f"{'rank':<5} {'cosine':>7} {'dot':>7}  document")
    print("-" * 70)
    for rank, (cosine, dot, text) in enumerate(scored, start=1):
        print(f"{rank:<5} {cosine:>7.3f} {dot:>7.3f}  {text}")


if __name__ == "__main__":
    main()