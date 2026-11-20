"""Entry point of the API: creates the FastAPI app, its error handlers and endpoints."""

import logging
import time
from contextlib import asynccontextmanager

import anthropic
import openai
import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from app.assistant import AssistantLoopError, ask_assistant
from app.config import get_settings
from app.llm_clients import (
    ProviderNotConfiguredError,
    call_anthropic,
    call_openai,
    start_openai_stream,
)
from app.logging_config import setup_logging
from app.prompts import PromptNotFoundError, load_prompt
from app.schemas import (
    AssistantRequest,
    AssistantResponse,
    ChatRequest,
    ChatResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
    StreamChatRequest,
    TriageRequest,
    TriageResponse,
)
from app.streaming import sse_events
from app.triage import TriageFailedError, triage_ticket
from app.db import DatabaseNotConfiguredError
from app.embeddings import warm_up
from app.search import search_chunks
from app.reranking import warm_up_reranker

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup (before `yield`) and once at shutdown (after `yield`)."""
    warm_up()
    warm_up_reranker()
    logger.info("models_ready")
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.4.0",
    description="Day 3: semantic search over the knowledge base",
    lifespan=lifespan,
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


@app.exception_handler(AssistantLoopError)
def handle_assistant_loop(request: Request, error: Exception) -> JSONResponse:
    return _error_response(
        request, 502, "assistant_loop_error",
        "The assistant could not finish answering. Please try again.", error,
        level=logging.ERROR,
    )


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

@app.exception_handler(DatabaseNotConfiguredError)
def handle_db_not_configured(request: Request, error: Exception) -> JSONResponse:
    return _error_response(
        request, 503, "database_not_configured",
        "Search is not configured on this server.", error, level=logging.ERROR,
    )


@app.exception_handler(psycopg.OperationalError)
def handle_db_unavailable(request: Request, error: Exception) -> JSONResponse:
    return _error_response(
        request, 503, "database_unavailable",
        "Search is temporarily unavailable. Please try again.", error,
        level=logging.ERROR,
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


@app.post("/chat/stream")
def chat_stream(request: StreamChatRequest) -> StreamingResponse:
    """Stream the reply as Server-Sent Events: one event per text chunk, then 'done'.

    Note: Swagger UI shows the whole response only at the end. Use curl or
    scripts/stream_client.py to see the chunks arrive live.
    """
    started_at = time.perf_counter()
    stream = start_openai_stream(
        request.message, system_prompt=load_prompt("chat", "v1")
    )
    return StreamingResponse(
        sse_events(stream, settings.openai_model, started_at),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.post("/assistant")
def assistant(request: AssistantRequest) -> AssistantResponse:
    """Answer a customer question, looking up order data with tools when needed."""
    outcome = ask_assistant(request.question)
    return AssistantResponse(
        reply=outcome.reply,
        tools_used=outcome.tools_used,
        steps=outcome.steps,
        input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens,
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

@app.post("/search")
def search(request: SearchRequest) -> SearchResponse:
    """Search knowledge base chunks: semantic, keyword or hybrid, optionally reranked."""
    outcome = search_chunks(
        request.query,
        request.top_k,
        request.category,
        mode=request.mode,
        chunk_config=request.chunk_config,
        rerank=request.rerank,
    )
    return SearchResponse(
        query=request.query,
        top_k=request.top_k,
        category=request.category,
        mode=outcome.mode,
        chunk_config=outcome.chunk_config,
        reranked=outcome.reranked,
        results=[
            SearchHit(
                source_id=hit.source_id,
                chunk_id=hit.chunk_id,
                slug=hit.slug,
                title=hit.title,
                category=hit.category,
                chunk_index=hit.chunk_index,
                content=hit.content,
                score=hit.score,
            )
            for hit in outcome.hits
        ],
        embedding_ms=outcome.embedding_ms,
        db_ms=outcome.db_ms,
        rerank_ms=outcome.rerank_ms,
    )