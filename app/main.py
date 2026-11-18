"""Entry point of the API: creates the FastAPI app, its error handlers and endpoints."""

import logging

import anthropic
import openai
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.llm_clients import ProviderNotConfiguredError, call_anthropic, call_openai
from app.logging_config import setup_logging
from app.schemas import ChatRequest, ChatResponse, TriageRequest, TriageResponse
from app.triage import TriageFailedError, triage_ticket
from app.prompts import PromptNotFoundError, load_prompt

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="Day 2: LLM backend with structured outputs",
)

PROVIDERS = {
    "openai": call_openai,
    "anthropic": call_anthropic,
}

logger.info(
    "app_starting",
    extra={
        "extra_fields": {
            "environment": settings.environment,
            "openai_configured": settings.openai_api_key is not None,
            "anthropic_configured": settings.anthropic_api_key is not None,
        }
    },
)


# ---------- Error handlers (shared by every endpoint) ----------


def _error_response(
    request: Request,
    status_code: int,
    event: str,
    message: str,
    error: Exception,
    level: int = logging.WARNING,
) -> JSONResponse:
    """Log the details for us, return a short safe message to the client."""
    logger.log(
        level,
        event,
        extra={
            "extra_fields": {
                "path": request.url.path,
                "error_type": type(error).__name__,
                "upstream_status": getattr(error, "status_code", None),
            }
        },
    )
    return JSONResponse(status_code=status_code, content={"detail": message})


@app.exception_handler(ProviderNotConfiguredError)
def handle_provider_not_configured(request: Request, error: Exception) -> JSONResponse:
    return _error_response(
        request, 503, "provider_not_configured",
        "The requested AI provider is not configured on this server.", error,
    )


@app.exception_handler(openai.APITimeoutError)
@app.exception_handler(anthropic.APITimeoutError)
def handle_timeout(request: Request, error: Exception) -> JSONResponse:
    return _error_response(
        request, 504, "llm_timeout",
        "The AI provider took too long to respond. Please try again.", error,
    )


@app.exception_handler(openai.RateLimitError)
@app.exception_handler(anthropic.RateLimitError)
def handle_rate_limit(request: Request, error: Exception) -> JSONResponse:
    return _error_response(
        request, 429, "llm_rate_limited",
        "Too many requests to the AI provider. Please wait and try again.", error,
    )


@app.exception_handler(openai.APIError)
@app.exception_handler(anthropic.APIError)
def handle_provider_error(request: Request, error: Exception) -> JSONResponse:
    return _error_response(
        request, 502, "llm_provider_error",
        "The AI provider returned an error.", error, level=logging.ERROR,
    )


@app.exception_handler(TriageFailedError)
def handle_triage_failed(request: Request, error: Exception) -> JSONResponse:
    return _error_response(
        request, 502, "triage_failed",
        "The AI could not produce a valid result. Please try again.", error,
        level=logging.ERROR,
    )


@app.exception_handler(PromptNotFoundError)
def handle_prompt_not_found(request: Request, error: Exception) -> JSONResponse:
    return _error_response(
        request, 500, "prompt_not_found",
        "Server configuration error.", error, level=logging.ERROR,
    )


# ---------- Endpoints ----------


@app.get("/health")
def health() -> dict[str, str | bool]:
    """Check that the server is alive and which LLM providers are configured."""
    logger.info("health_checked")
    return {
        "status": "ok",
        "environment": settings.environment,
        "openai_configured": settings.openai_api_key is not None,
        "anthropic_configured": settings.anthropic_api_key is not None,
    }


@app.post("/chat")
def chat(request: ChatRequest) -> ChatResponse:
    """Send one message to the chosen LLM provider and return its reply."""
    call_llm = PROVIDERS[request.provider]
    result = call_llm(request.message, system_prompt=load_prompt("chat", "v1"))
    return ChatResponse(
        provider=result.provider,
        model=result.model,
        reply=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )


@app.post("/triage")
def triage(request: TriageRequest) -> TriageResponse:
    """Classify a support ticket into validated, structured JSON."""
    outcome = triage_ticket(request.ticket, request.prompt_version)
    return TriageResponse(
        result=outcome.result,
        prompt_version=request.prompt_version,
        model=outcome.model,
        attempts=outcome.attempts,
        input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens,
        latency_ms=outcome.latency_ms,
    )