"""Turn an LLM token stream into Server-Sent Events (SSE) for our clients."""

import json
import logging
import time
from collections.abc import Iterator
from typing import Any

import openai
from openai import Stream
from openai.types.chat import ChatCompletionChunk

logger = logging.getLogger(__name__)


def _sse(data: dict[str, Any]) -> str:
    """Format one Server-Sent Event: a 'data:' line with JSON, then a blank line."""
    return f"data: {json.dumps(data)}\n\n"


def sse_events(
    stream: Stream[ChatCompletionChunk], model: str, started_at: float
) -> Iterator[str]:
    """Yield one SSE event per text chunk, then a final 'done' event with timings."""
    first_token_ms: float | None = None
    chunks = 0

    try:
        for chunk in stream:
            if not chunk.choices:
                continue
            text = chunk.choices[0].delta.content
            if not text:
                continue

            if first_token_ms is None:
                first_token_ms = round((time.perf_counter() - started_at) * 1000, 1)
            chunks += 1
            yield _sse({"delta": text})

    except openai.APIError as error:
        logger.error(
            "stream_failed",
            extra={"extra_fields": {"error_type": type(error).__name__, "chunks": chunks}},
        )
        yield _sse({"error": "The AI provider failed while streaming. Please try again."})
        return

    finally:
        stream.close()

    total_ms = round((time.perf_counter() - started_at) * 1000, 1)
    logger.info(
        "stream_completed",
        extra={
            "extra_fields": {
                "model": model,
                "time_to_first_token_ms": first_token_ms,
                "total_ms": total_ms,
                "chunks": chunks,
            }
        },
    )
    yield _sse(
        {
            "done": True,
            "model": model,
            "time_to_first_token_ms": first_token_ms,
            "total_ms": total_ms,
            "chunks": chunks,
        }
    )