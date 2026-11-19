"""Request and response shapes for the API, validated by Pydantic."""

from typing import Literal
from app.streaming import sse_events
from pydantic import BaseModel, Field
from pydantic import BaseModel, ConfigDict, Field

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

class TriageResult(BaseModel):
    """The exact JSON the model must return for one ticket."""

    model_config = ConfigDict(extra="forbid")

    category: Literal["billing", "shipping", "technical", "account", "other"]
    priority: Literal["low", "medium", "high", "urgent"]
    sentiment: Literal["positive", "neutral", "negative", "angry"]
    summary: str = Field(min_length=1, max_length=300)
    needs_human: bool


class TriageRequest(BaseModel):
    """What the client sends to /triage."""

    ticket: str = Field(
        min_length=1,
        max_length=4000,
        description="The customer's support message.",
        examples=[
            "I was charged twice for order #4521 and nobody has answered my emails!"
        ],
    )
    prompt_version: Literal["v1", "v2", "v3", "v4"] = Field(
        default="v4",
        description="Which triage prompt version to use.",
    )


class TriageResponse(BaseModel):
    """What /triage sends back."""

    result: TriageResult
    prompt_version: str
    model: str
    attempts: int
    input_tokens: int 
    output_tokens: int
    latency_ms: float    


class AssistantRequest(BaseModel):
    """What the client sends to /assistant."""

    question: str = Field(
        min_length=1,
        max_length=2000,
        description="The customer's question.",
        examples=["What's the status of my order #4521?"],
    )


class AssistantResponse(BaseModel):
    """What /assistant sends back."""

    reply: str
    tools_used: list[str]
    steps: int
    input_tokens: int
    output_tokens: int

class StreamChatRequest(BaseModel):
    """What the client sends to /chat/stream."""

    message: str = Field(
        min_length=1,
        max_length=4000,
        description="The user's question or instruction.",
        examples=["Explain what a Forward Deployed Engineer does in 3 short paragraphs."],
    )


class SearchRequest(BaseModel):
    """What the client sends to /search."""

    query: str = Field(
        min_length=1,
        max_length=500,
        description="The question or search text.",
        examples=["How do I get my money back?"],
    )
    top_k: int = Field(default=5, ge=1, le=20, description="How many results to return.")
    category: Literal["billing", "shipping", "technical", "account", "other"] | None = Field(
        default=None,
        description="Only search documents in this category (optional).",
    )


class SearchHit(BaseModel):
    """One search result."""

    slug: str
    title: str
    content: str
    category: str
    similarity: float


class SearchResponse(BaseModel):
    """What /search sends back."""

    query: str
    top_k: int
    category: str | None
    results: list[SearchHit]
    embedding_ms: float
    db_ms: float