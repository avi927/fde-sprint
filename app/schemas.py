"""Request and response shapes for the API, validated by Pydantic."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """What the client sends to /chat."""

    message: str = Field(
        min_length=1,
        max_length=4000,
        description="The user's question or instruction.",
        examples=["In one sentence, what is a Forward Deployed Engineer?"],
    )
    provider: Literal["openai", "anthropic"] = Field(
        default="openai",
        description="Which LLM provider to use.",
    )


class ChatResponse(BaseModel):
    """What /chat sends back."""

    provider: str
    model: str
    reply: str
    input_tokens: int
    output_tokens: int
    latency_ms: float