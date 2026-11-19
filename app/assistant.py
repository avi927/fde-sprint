"""A support assistant that can call tools: the basic tool-calling loop."""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings
from app.llm_clients import get_openai_client
from app.prompts import load_prompt
from app.tools import run_tool, tool_definitions

logger = logging.getLogger(__name__)

MAX_STEPS = 5


class AssistantLoopError(Exception):
    """Raised when the assistant keeps calling tools without giving a final answer."""


@dataclass(frozen=True)
class AssistantReply:
    """The final answer plus what happened along the way."""

    reply: str
    steps: int
    input_tokens: int
    output_tokens: int
    tools_used: list[str] = field(default_factory=list)


def ask_assistant(question: str) -> AssistantReply:
    """Answer one customer question, calling tools when the model asks for them."""
    settings = get_settings()
    client = get_openai_client()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": load_prompt("assistant", "v1")},
        {"role": "user", "content": question},
    ]
    tools_used: list[str] = []
    input_tokens = 0
    output_tokens = 0

    for step in range(1, MAX_STEPS + 1):
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            tools=tool_definitions(),
            max_completion_tokens=settings.llm_max_output_tokens,
        )
        if response.usage:
            input_tokens += response.usage.prompt_tokens
            output_tokens += response.usage.completion_tokens

        message = response.choices[0].message

        # No tool calls means the model gave its final answer.
        if not message.tool_calls:
            logger.info(
                "assistant_completed",
                extra={"extra_fields": {"steps": step, "tools_used": tools_used}},
            )
            return AssistantReply(
                reply=message.content or "",
                steps=step,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tools_used=tools_used,
            )

        # The model asked for tools: remember its request in the conversation...
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in message.tool_calls
                ],
            }
        )

        # ...then run each tool and add its result, linked by the call's id.
        for call in message.tool_calls:
            tools_used.append(call.function.name)
            result = run_tool(call.function.name, call.function.arguments)
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )

    logger.error("assistant_step_limit", extra={"extra_fields": {"steps": MAX_STEPS}})
    raise AssistantLoopError(f"No final answer after {MAX_STEPS} steps")