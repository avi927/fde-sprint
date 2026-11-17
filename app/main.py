"""Entry point of the API: creates the FastAPI app and its endpoints."""

import logging

import anthropic
import openai
from fastapi import FastAPI, HTTPException

from app.config import get_settings
from app.llm_clients import ProviderNotConfiguredError, call_anthropic, call_openai
from app.logging_config import setup_logging
from app.schemas import ChatRequest, ChatResponse

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Day 1: LLM backend",
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

    try:
        result = call_llm(request.message)

    except ProviderNotConfiguredError as error:
        logger.warning(
            "provider_not_configured",
            extra={"extra_fields": {"provider": request.provider}},
        )
        raise HTTPException(
            status_code=503,
            detail=f"Provider '{request.provider}' is not configured on this server.",
        ) from error

    except (openai.APITimeoutError, anthropic.APITimeoutError) as error:
        logger.warning(
            "llm_timeout",
            extra={"extra_fields": {"provider": request.provider}},
        )
        raise HTTPException(
            status_code=504,
            detail="The AI provider took too long to respond. Please try again.",
        ) from error

    except (openai.RateLimitError, anthropic.RateLimitError) as error:
        logger.warning(
            "llm_rate_limited",
            extra={"extra_fields": {"provider": request.provider}},
        )
        raise HTTPException(
            status_code=429,
            detail="Too many requests to the AI provider. Please wait and try again.",
        ) from error

    except (openai.APIError, anthropic.APIError) as error:
        logger.error(
            "llm_provider_error",
            extra={
                "extra_fields": {
                    "provider": request.provider,
                    "error_type": type(error).__name__,
                    "upstream_status": getattr(error, "status_code", None),
                }
            },
        )
        raise HTTPException(
            status_code=502,
            detail="The AI provider returned an error.",
        ) from error

    return ChatResponse(
        provider=result.provider,
        model=result.model,
        reply=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )