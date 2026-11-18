"""Ticket triage: prompt the LLM, validate its JSON, retry with feedback when invalid."""

import logging
from dataclasses import dataclass

from pydantic import ValidationError

from app.llm_clients import call_openai
from app.prompts import load_prompt
from app.schemas import TriageResult

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


class TriageFailedError(Exception):
    """Raised when the model never returns valid triage JSON."""


@dataclass(frozen=True)
class TriageOutcome:
    """A validated triage result plus usage totals across all attempts."""

    result: TriageResult
    model: str
    attempts: int
    input_tokens: int
    output_tokens: int
    latency_ms: float


def triage_ticket(ticket: str, prompt_version: str = "v3") -> TriageOutcome:
    """Classify one support ticket, retrying until the JSON is valid."""
    system_prompt = load_prompt("triage", prompt_version)
    ticket_message = f"<ticket>\n{ticket}\n</ticket>"
    prompt = ticket_message

    total_input_tokens = 0
    total_output_tokens = 0
    total_latency_ms = 0.0
    model = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        llm_result = call_openai(prompt, system_prompt=system_prompt)
        total_input_tokens += llm_result.input_tokens
        total_output_tokens += llm_result.output_tokens
        total_latency_ms += llm_result.latency_ms
        model = llm_result.model

        try:
            result = TriageResult.model_validate_json(
                _strip_code_fences(llm_result.text)
            )
        except ValidationError as error:
            logger.warning(
                "triage_invalid_output",
                extra={
                    "extra_fields": {
                        "attempt": attempt,
                        "prompt_version": prompt_version,
                        "error_count": error.error_count(),
                    }
                },
            )
            prompt = _build_retry_prompt(ticket_message, error)
            continue

        logger.info(
            "triage_completed",
            extra={
                "extra_fields": {
                    "attempts": attempt,
                    "prompt_version": prompt_version,
                    "category": result.category,
                    "priority": result.priority,
                }
            },
        )
        return TriageOutcome(
            result=result,
            model=model,
            attempts=attempt,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            latency_ms=round(total_latency_ms, 1),
        )

    raise TriageFailedError(f"No valid triage output after {MAX_ATTEMPTS} attempts")


def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` fences if the model added them."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[len("json"):]
    return cleaned.strip()


def _build_retry_prompt(ticket_message: str, error: ValidationError) -> str:
    """Repeat the ticket and explain exactly what was wrong with the last answer."""
    problems = []
    for issue in error.errors():
        field = ".".join(str(part) for part in issue["loc"]) or "response"
        problems.append(f"- {field}: {issue['msg']}")

    problem_lines = "\n".join(problems)
    return (
        f"{ticket_message}\n\n"
        f"Your previous answer was not valid. Problems found:\n{problem_lines}\n\n"
        "Return ONLY the JSON object, with exactly the required fields and allowed values."
    )