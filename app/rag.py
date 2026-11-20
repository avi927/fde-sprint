"""Retrieval-Augmented Generation: retrieve chunks, build context, answer with validated citations."""

import logging
import re
import time
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import get_settings
from app.context import build_context, sanitize
from app.llm_clients import call_openai
from app.prompts import load_prompt
from app.search import ChunkHit, search_chunks
from app.text_utils import strip_code_fences

logger = logging.getLogger(__name__)

IDK_ANSWER = "I don't know based on the available help articles."
MAX_ATTEMPTS = 3
_CITATION = re.compile(r"\[([a-z0-9-]+#\d+)\]")


class RagFailedError(Exception):
    """Raised when the model never returns a valid, properly cited answer."""


class RagModelOutput(BaseModel):
    """The JSON the model must return."""

    model_config = ConfigDict(extra="forbid")

    answerable: bool
    answer: str = Field(min_length=1, max_length=2000)


@dataclass(frozen=True)
class RagOutcome:
    """The final answer plus everything needed to inspect and evaluate it."""

    answer: str
    answerable: bool
    citations: list[str]
    sources: list[ChunkHit]
    attempts: int
    retrieval_ms: float
    llm_ms: float
    input_tokens: int
    output_tokens: int


def _normalize(answer: str) -> str:
    """Trim spaces and turn curly apostrophes into straight ones."""
    return answer.strip().replace("\u2019", "'")


def extract_citations(answer: str) -> list[str]:
    """Unique [source-id] citations, in order of first appearance."""
    return list(dict.fromkeys(_CITATION.findall(answer)))


def check_answer(output: RagModelOutput, allowed: set[str]) -> list[str]:
    """Return the problems with an answer (an empty list means it's valid)."""
    answer = _normalize(output.answer)
    citations = extract_citations(answer)
    problems: list[str] = []

    unknown = [citation for citation in citations if citation not in allowed]
    if unknown:
        problems.append(f"These citations are not in the context: {', '.join(unknown)}")
    if output.answerable and answer == IDK_ANSWER:
        problems.append('"answerable" must be false when the answer is that you don\'t know.')
    elif output.answerable and not citations:
        problems.append("An answer must cite at least one source id in [square brackets].")
    if not output.answerable and answer != IDK_ANSWER:
        problems.append(f'When "answerable" is false, "answer" must be exactly: {IDK_ANSWER}')
    return problems


def _idk(sources: list[ChunkHit], attempts: int, retrieval_ms: float) -> RagOutcome:
    """An 'I don't know' outcome without calling the LLM."""
    return RagOutcome(
        answer=IDK_ANSWER,
        answerable=False,
        citations=[],
        sources=sources,
        attempts=attempts,
        retrieval_ms=retrieval_ms,
        llm_ms=0.0,
        input_tokens=0,
        output_tokens=0,
    )


def answer_question(
    question: str,
    mode: str | None = None,
    rerank: bool | None = None,
    chunk_config: str | None = None,
) -> RagOutcome:
    """Answer a question from the knowledge base, with citations, or say I don't know.

    mode / rerank / chunk_config default to the server config (None = use config).
    """
    settings = get_settings()
    mode = mode or settings.rag_search_mode
    rerank = settings.rag_rerank if rerank is None else rerank

    # 1. Retrieve
    start = time.perf_counter()
    search = search_chunks(
        question,
        top_k=settings.rag_top_k,
        mode=mode,
        rerank=rerank,
        chunk_config=chunk_config,
    )
    retrieval_ms = round((time.perf_counter() - start) * 1000, 1)

    # 2. Build the context
    context = build_context(search.hits, max_words=settings.rag_max_context_words)
    if not context.hits:
        logger.info("rag_no_context")
        return _idk([], attempts=0, retrieval_ms=retrieval_ms)

    # 3. Generate, 4. validate (retry with feedback)
    system_prompt = load_prompt("rag", "v1")
    base_message = f"{context.text}\n\n<question>\n{sanitize(question)}\n</question>"
    allowed = set(context.source_ids)
    message = base_message
    llm_ms = 0.0
    input_tokens = 0
    output_tokens = 0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = call_openai(message, system_prompt=system_prompt)
        llm_ms += result.latency_ms
        input_tokens += result.input_tokens
        output_tokens += result.output_tokens

        try:
            output = RagModelOutput.model_validate_json(strip_code_fences(result.text))
            problems = check_answer(output, allowed)
        except ValidationError as error:
            problems = [
                f"{'.'.join(str(part) for part in issue['loc']) or 'response'}: {issue['msg']}"
                for issue in error.errors()
            ]

        if not problems:
            answer = _normalize(output.answer)
            citations = extract_citations(answer)
            logger.info(
                "rag_completed",
                extra={
                    "extra_fields": {
                        "mode": mode,
                        "rerank": rerank,
                        "chunk_config": search.chunk_config,
                        "answerable": output.answerable,
                        "citations": len(citations),
                        "context_chunks": len(context.hits),
                        "dropped_duplicates": context.dropped_duplicates,
                        "dropped_budget": context.dropped_budget,
                        "attempts": attempt,
                        "retrieval_ms": retrieval_ms,
                        "llm_ms": round(llm_ms, 1),
                    }
                },
            )
            return RagOutcome(
                answer=answer,
                answerable=output.answerable,
                citations=citations,
                sources=context.hits,
                attempts=attempt,
                retrieval_ms=retrieval_ms,
                llm_ms=round(llm_ms, 1),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        logger.warning(
            "rag_invalid_output",
            extra={"extra_fields": {"attempt": attempt, "problems": len(problems)}},
        )
        feedback = "\n".join(f"- {problem}" for problem in problems)
        message = (
            f"{base_message}\n\nYour previous answer was not valid. Problems:\n{feedback}\n\n"
            "Return ONLY the JSON object, following all the rules."
        )

    raise RagFailedError(f"No valid answer after {MAX_ATTEMPTS} attempts")