"""Run one ticket through every version of the triage prompt and print the raw output."""

import sys

from app.llm_clients import call_openai
from app.logging_config import setup_logging
from app.prompts import load_prompt

VERSIONS = ["v1", "v2", "v3"]

DEFAULT_TICKET = (
    "I was charged twice for order #4521 and nobody has answered my last 3 emails. "
    "Fix this today or I'm disputing it with my bank!"
)


def main() -> None:
    setup_logging("WARNING")
    ticket = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TICKET
    user_message = f"<ticket>\n{ticket}\n</ticket>"

    for version in VERSIONS:
        system_prompt = load_prompt("triage", version)
        result = call_openai(user_message, system_prompt=system_prompt)
        print(f"\n===== triage_{version} =====")
        print(result.text)
        print(
            f"[tokens in/out: {result.input_tokens}/{result.output_tokens}"
            f" | {result.latency_ms} ms]"
        )


if __name__ == "__main__":
    main()