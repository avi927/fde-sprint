"""Run the triage eval: every test case through every prompt version, then score."""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.logging_config import setup_logging
from app.triage import TriageFailedError, triage_ticket

ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = ROOT / "evals" / "triage_cases.json"
RESULTS_DIR = ROOT / "evals" / "results"

SCORED_FIELDS = ["category", "priority", "sentiment", "needs_human"]
DEFAULT_VERSIONS = ["v1", "v2", "v3"]
PAUSE_SECONDS = 2.0


def is_match(actual: object, expected: object) -> bool:
    """A field matches if it equals the expected value, or is one of a list of values."""
    if isinstance(expected, list):
        return actual in expected
    return actual == expected


def run_version(version: str, cases: list[dict]) -> dict:
    """Run every case through one prompt version and return its scores."""
    field_hits = {field: 0 for field in SCORED_FIELDS}
    mistakes = []
    perfect = 0
    failed = 0
    total_attempts = 0
    total_input_tokens = 0
    total_latency_ms = 0.0

    for case in cases:
        time.sleep(PAUSE_SECONDS)
        print(f"  {version} · {case['id']}")

        try:
            outcome = triage_ticket(case["ticket"], version)
        except TriageFailedError:
            failed += 1
            mistakes.append({"id": case["id"], "problem": "no valid JSON after retries"})
            continue

        total_attempts += outcome.attempts
        total_input_tokens += outcome.input_tokens
        total_latency_ms += outcome.latency_ms

        actual = outcome.result.model_dump()
        wrong_fields = []
        for field in SCORED_FIELDS:
            if is_match(actual[field], case["expected"][field]):
                field_hits[field] += 1
            else:
                wrong_fields.append(field)
                mistakes.append({
                    "id": case["id"],
                    "field": field,
                    "expected": case["expected"][field],
                    "actual": actual[field],
                })

        if not wrong_fields:
            perfect += 1

    total = len(cases)
    succeeded = total - failed
    return {
        "version": version,
        "cases": total,
        "perfect": perfect,
        "field_accuracy": {field: field_hits[field] / total for field in SCORED_FIELDS},
        "failed": failed,
        "avg_attempts": total_attempts / succeeded if succeeded else 0,
        "total_input_tokens": total_input_tokens,
        "avg_latency_ms": total_latency_ms / succeeded if succeeded else 0,
        "mistakes": mistakes,
    }


def print_report(summaries: list[dict]) -> None:
    """Print a score table plus every mistake."""
    print("\n" + "=" * 100)
    print(
        f"{'version':<8} {'perfect':>8} {'category':>9} {'priority':>9} "
        f"{'sentiment':>10} {'human':>7} {'failed':>7} {'attempts':>9} "
        f"{'in tokens':>10} {'avg ms':>8}"
    )
    print("-" * 100)
    for s in summaries:
        acc = s["field_accuracy"]
        print(
            f"{s['version']:<8} {s['perfect']:>5}/{s['cases']:<2} "
            f"{acc['category']:>9.0%} {acc['priority']:>9.0%} "
            f"{acc['sentiment']:>10.0%} {acc['needs_human']:>7.0%} "
            f"{s['failed']:>7} {s['avg_attempts']:>9.2f} "
            f"{s['total_input_tokens']:>10} {s['avg_latency_ms']:>8.0f}"
        )
    print("=" * 100)

    for s in summaries:
        print(f"\nMistakes for {s['version']}:")
        if not s["mistakes"]:
            print("  none 🎉")
        for m in s["mistakes"]:
            if "problem" in m:
                print(f"  - {m['id']}: {m['problem']}")
            else:
                print(
                    f"  - {m['id']}: {m['field']} expected {m['expected']}, "
                    f"got {m['actual']!r}"
                )


def main() -> None:
    setup_logging("ERROR")
    versions = sys.argv[1:] or DEFAULT_VERSIONS
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    print(f"Running {len(cases)} cases through {versions}...")

    summaries = [run_version(version, cases) for version in versions]
    print_report(summaries)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_file = RESULTS_DIR / f"triage_{timestamp}.json"
    out_file.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"\nSaved results to {out_file.relative_to(ROOT)}")


if __name__ == "__main__":
    main()