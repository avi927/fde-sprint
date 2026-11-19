"""Thin wrappers around the OpenAI and Anthropic SDKs, with timing and token logging."""

import logging
import time
from dataclasses import dataclass

from anthropic import Anthropic
from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "You are a concise, helpful assistant. Answer in plain language."
class ProviderNotConfiguredError(Exception):
    """Raised when a provider's API key is missing from the config."""

@dataclass(frozen=True)
class LLMResult:
    """The same result shape, no matter which provider answered."""

    provider: str
    model: str
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float

def get_openai_client() -> OpenAI:
    """Create an OpenAI SDK client from settings (works for OpenAI-compatible providers too)."""
    settings = get_settings()
    if settings.openai_api_key is None:
        raise ProviderNotConfiguredError("OPENAI_API_KEY is not set in .env")
    return OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        base_url=settings.openai_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=2,
    )


def call_openai(prompt: str, system_prompt: str = SYSTEM_PROMPT) -> LLMResult:
    """Call OpenAI, or any OpenAI-compatible provider such as Groq."""
    settings = get_settings()
    client = get_openai_client()

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_completion_tokens=settings.llm_max_output_tokens,
    )
    latency_ms = (time.perf_counter() - start) * 1000

    result = LLMResult(
        provider="openai" if settings.openai_base_url is None else "openai-compatible",
        model=settings.openai_model,
        text=response.choices[0].message.content or "",
        input_tokens=response.usage.prompt_tokens if response.usage else 0,
        output_tokens=response.usage.completion_tokens if response.usage else 0,
        latency_ms=round(latency_ms, 1),
    )
    _log_result(result)
    return result


def call_anthropic(prompt: str, system_prompt: str = SYSTEM_PROMPT) -> LLMResult:
    """Call Anthropic's Claude with one user prompt."""
    settings = get_settings()
    if settings.anthropic_api_key is None:
        raise ValueError("ANTHROPIC_API_KEY is not set in .env")

    client = Anthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        timeout=settings.llm_timeout_seconds,
        max_retries=2,
    )

    start = time.perf_counter()
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.llm_max_output_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    latency_ms = (time.perf_counter() - start) * 1000

    text = "".join(block.text for block in response.content if block.type == "text")

    result = LLMResult(
        provider="anthropic",
        model=settings.anthropic_model,
        text=text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=round(latency_ms, 1),
    )
    _log_result(result)
    return result


def _log_result(result: LLMResult) -> None:
    """Log the metadata of a call. Never the prompt or answer text."""
    logger.info(
        "llm_call_completed",
        extra={
            "extra_fields": {
                "provider": result.provider,
                "model": result.model,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "latency_ms": result.latency_ms,
            }
        },
    )