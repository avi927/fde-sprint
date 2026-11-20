"""Compare keyword vs semantic search (with and without the query prefix) on a golden set."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.logging_config import setup_logging
from app.search import search_documents

ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = ROOT / "evals" / "search_cases.json"
RESULTS_DIR = ROOT / "evals" / "results"
TOP_K = 5

CONFIGS: dict[str, dict[str, Any]] = {
    "keyword": {"mode": "keyword"},
    "semantic_no_prefix": {"mode": "semantic", "use_prefix": False},
    "semantic_prefix": {"mode": "semantic", "use_prefix": True},
}


def first_relevant_rank(result_slugs: list[str], relevant: list[str]) -> int | None:
    """Position (1-based) of the first relevant result, or None if none was returned."""
    for rank, slug in enumerate(result_slugs, start=1):
        if slug in relevant:
            return rank
    return None


def evaluate(name: str, options: dict[str, Any], cases: list[dict]) -> dict[str, Any]:
    """Run every case with one configuration and compute Hit@1, Hit@3 and MRR."""
    hits_at_1 = 0
    hits_at_3 = 0
    reciprocal_ranks = []
    details = []

    for case in cases:
        outcome = search_documents(case["query"], top_k=TOP_K, **options)
        slugs = [hit.slug for hit in outcome.hits]
        rank = first_relevant_rank(slugs, case["relevant"])

        if rank == 1:
            hits_at_1 += 1
        if rank is not None and rank <= 3:
            hits_at_3 += 1
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        details.append(
            {"id": case["id"], "rank": rank, "top_1": slugs[0] if slugs else None}
        )

    total = len(cases)
    return {
        "config": name,
        "hit_at_1": hits_at_1 / total,
        "hit_at_3": hits_at_3 / total,
        "mrr": sum(reciprocal_ranks) / total,
        "details": details,
    }


def print_report(results: list[dict[str, Any]], cases: list[dict]) -> None:
    """Print the summary table, then the rank of the right answer per query and method."""
    print("\n" + "=" * 60)
    print(f"{'config':<22} {'Hit@1':>8} {'Hit@3':>8} {f'MRR@{TOP_K}':>8}")
    print("-" * 60)
    for r in results:
        print(f"{r['config']:<22} {r['hit_at_1']:>8.0%} {r['hit_at_3']:>8.0%} {r['mrr']:>8.2f}")
    print("=" * 60)

    print(f"\nRank of the correct article per query (- = not in top {TOP_K}):\n")
    header = f"{'query id':<22}" + "".join(f"{r['config']:>20}" for r in results)
    print(header)
    print("-" * len(header))
    for i, case in enumerate(cases):
        row = f"{case['id']:<22}"
        for r in results:
            detail = r["details"][i]
            cell = str(detail["rank"]) if detail["rank"] else f"- ({detail['top_1']})"
            row += f"{cell:>20}"
        print(row)


def main() -> None:
    setup_logging("WARNING")
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    print(f"Evaluating {len(cases)} queries, top_k={TOP_K}, configs: {list(CONFIGS)}")

    results = [evaluate(name, options, cases) for name, options in CONFIGS.items()]
    print_report(results, cases)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_file = RESULTS_DIR / f"search_{timestamp}.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved results to {out_file.relative_to(ROOT)}")


if __name__ == "__main__":
    main()