"""Quick manual check: call both LLM providers from the terminal."""

from app.config import get_settings
from app.llm_clients import call_anthropic, call_openai
from app.logging_config import setup_logging


def main() -> None:
    setup_logging(get_settings().log_level)
    prompt = "In one sentence, what is a Forward Deployed Engineer?"

    for call in (call_openai, call_anthropic):
        try:
            result = call(prompt)
            print(f"\n=== {result.provider} ({result.model}) ===")
            print(result.text)
            print(
                f"tokens in/out: {result.input_tokens}/{result.output_tokens}"
                f" | latency: {result.latency_ms} ms"
            )
        except Exception as error:
            print(f"\n{call.__name__} FAILED: {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()