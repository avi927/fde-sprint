"""Entry point of the API: creates the FastAPI app and its endpoints."""

import logging

from fastapi import FastAPI

from app.config import get_settings
from app.logging_config import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Day 1: LLM backend",
)

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