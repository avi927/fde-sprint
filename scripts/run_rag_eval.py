"""RAG eval: does /ask find the right text, answer correctly, cite properly, and refuse when it should?"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import openai

from app.logging_config import setup_logging
from app.rag import RagFailedError, RagOutcome, answer_question

ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = ROOT / "evals" / "rag_cases.json"
RESULTS_DIR = ROOT / "evals" / "results"
PAUSE_SECONDS = 3.0

CONFIGS: dict[str, dict[str, Any]] = {
    "semantic_small": {"mode": "semantic", "rerank": False, "chunk_config": "small"},
    "hybrid_rerank_small": {"mode": "hybrid", "rerank": True, "chunk_config": "small"},
    "hybrid_rerank_large": {"mode": "hybrid", "rerank": True, "chunk_config": "large"},
}


def contains_all(text: str, facts: list[str]) -> bool:
    """True if every fact appears in the text (case-insensitive).

    A fact can list alternatives separated by '|', e.g. "31 January|January 31".
    """
    lowered = text.lower()
    return all(
        any(option.strip().lower() in lowered for option in fact.split("|"))
        for fact in facts
    )


def score_case(case: dict[str, Any], outcome: RagOutcome) -> dict[str, Any]:
    """Score one answer and diagnose which stage failed, if any."""
    context_text = " ".join(hit.content for hit in outcome.sources)
    cited_docs = {citation.split("#")[0] for citation in outcome.citations}
    expected_docs = set(case["expected_sources"])
    facts = case["must_include"]

    if case["answerable"]:
        fact_in_context = contains_all(context_text, facts)
        facts_in_answer = contains_all(outcome.answer, facts)
        citation_ok = bool(cited_docs & expected_docs)

        if not fact_in_context:
            diagnosis = "retrieval_miss"
        elif not outcome.answerable:
            diagnosis = "false_idk"
        elif not facts_in_answer:
            diagnosis = "wrong_answer"
        elif not citation_ok:
            diagnosis = "bad_citation"
        else:
            diagnosis = "ok"
    else:
        fact_in_context = None
        facts_in_answer = None
        citation_ok = not outcome.citations
        diagnosis = "hallucinated_answer" if outcome.answerable else "ok"

    return {
        "id": case["id"],
        "diagnosis": diagnosis,
        "fact_in_context": fact_in_context,
        "facts_in_answer": facts_in_answer,
        "citation_ok": citation_ok,
        "answerable": outcome.answerable,
        "answer": outcome.answer,
        "citations": outcome.citations,
        "attempts": outcome.attempts,
        "input_tokens": outcome.input_tokens,
        "retrieval_ms": outcome.retrieval_ms,
        "llm_ms": outcome.llm_ms,
    }


def run_config(name: str, options: dict[str, Any], cases: list[dict]) -> list[dict[str, Any]]:
    """Answer every question with one configuration."""
    rows = []
    for case in cases:
        time.sleep(PAUSE_SECONDS)
        print(f"  {name} · {case['id']}")
        try:
            outcome = answer_question(case["question"], **options)
            rows.append(score_case(case, outcome))
        except RagFailedError:
            rows.append({"id": case["id"], "diagnosis": "failed"})
        except openai.RateLimitError:
            rows.append({"id": case["id"], "diagnosis": "rate_limited"})
    return rows


def summarize(name: str, rows: list[dict[str, Any]], cases: list[dict]) -> dict[str, Any]:
    """Aggregate one configuration's rows into headline numbers."""
    answerable_ids = {case["id"] for case in cases if case["answerable"]}
    scored = [row for row in rows if "input_tokens" in row]
    retrieved = [
        row for row in scored if row["id"] in answerable_ids and row["fact_in_context"]
    ]

    def average(key: str) -> float:
        return sum(row[key] for row in scored) / len(scored) if scored else 0.0

    return {
        "config": name,
        "ok": sum(row["diagnosis"] == "ok" for row in rows),
        "total": len(rows),
        "retrieval_rate": len(retrieved) / len(answerable_ids),
        "hallucinated": sum(row["diagnosis"] == "hallucinated_answer" for row in rows),
        "false_idk": sum(row["diagnosis"] == "false_idk" for row in rows),
        "avg_input_tokens": average("input_tokens"),
        "avg_retrieval_ms": average("retrieval_ms"),
        "avg_llm_ms": average("llm_ms"),
        "rows": rows,
    }


def print_report(summaries: list[dict[str, Any]], cases: list[dict]) -> None:
    """Summary table, then the diagnosis of every question per configuration."""
    print("\n" + "=" * 96)
    print(
        f"{'config':<22} {'ok':>6} {'retrieval':>10} {'halluc.':>8} {'false IDK':>10} "
        f"{'in tokens':>10} {'retr ms':>8} {'llm ms':>8}"
    )
    print("-" * 96)
    for s in summaries:
        print(
            f"{s['config']:<22} {s['ok']:>3}/{s['total']:<2} {s['retrieval_rate']:>10.0%} "
            f"{s['hallucinated']:>8} {s['false_idk']:>10} {s['avg_input_tokens']:>10.0f} "
            f"{s['avg_retrieval_ms']:>8.0f} {s['avg_llm_ms']:>8.0f}"
        )
    print("=" * 96)

    print("\nDiagnosis per question:\n")
    header = f"{'question id':<24}" + "".join(f"{s['config']:>24}" for s in summaries)
    print(header)
    print("-" * len(header))
    for i, case in enumerate(cases):
        row = f"{case['id']:<24}"
        for s in summaries:
            row += f"{s['rows'][i]['diagnosis']:>24}"
        print(row)


def main() -> None:
    setup_logging("ERROR")
    names = sys.argv[1:] or list(CONFIGS)
    unknown = [name for name in names if name not in CONFIGS]
    if unknown:
        raise SystemExit(f"Unknown config(s): {unknown}. Choose from {list(CONFIGS)}")

    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    print(f"Running {len(cases)} questions through {names} ({PAUSE_SECONDS}s pause per call)...")

    summaries = [summarize(name, run_config(name, CONFIGS[name], cases), cases) for name in names]
    print_report(summaries, cases)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_file = RESULTS_DIR / f"rag_{timestamp}.json"
    out_file.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"\nSaved results to {out_file.relative_to(ROOT)}")


if __name__ == "__main__":
    main()