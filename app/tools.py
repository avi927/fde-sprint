"""Tools the assistant can call, with their JSON schemas for the LLM."""

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# Fake order database. On a real project this would be the customer's order system.
FAKE_ORDERS: dict[str, dict[str, str]] = {
    "4521": {"status": "shipped", "carrier": "DHL", "expected_delivery": "2026-11-21"},
    "7781": {"status": "returned", "refund_status": "pending"},
    "3310": {"status": "delivered", "delivered_on": "2026-11-12"},
}


class GetOrderStatusArgs(BaseModel):
    """Arguments for get_order_status, validated before the tool runs."""

    order_id: str = Field(
        pattern=r"^\d{4}$",
        description="The 4-digit order number, without the # sign. Example: 4521",
    )


def get_order_status(args: GetOrderStatusArgs) -> dict[str, Any]:
    """Look up one order. Read-only: it never changes anything."""
    order = FAKE_ORDERS.get(args.order_id)
    if order is None:
        return {"found": False, "order_id": args.order_id}
    return {"found": True, "order_id": args.order_id, **order}


@dataclass(frozen=True)
class Tool:
    """Everything we need to offer a tool to the model and run it safely."""

    name: str
    description: str
    args_model: type[BaseModel]
    function: Callable[[Any], dict[str, Any]]


TOOLS: dict[str, Tool] = {
    "get_order_status": Tool(
        name="get_order_status",
        description="Look up the current status of a customer's order by its order number.",
        args_model=GetOrderStatusArgs,
        function=get_order_status,
    ),
}


def tool_definitions() -> list[dict[str, Any]]:
    """The tool menu in the format the OpenAI Chat Completions API expects."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.args_model.model_json_schema(),
            },
        }
        for tool in TOOLS.values()
    ]


def run_tool(name: str, arguments_json: str) -> str:
    """Validate the model's arguments, run the tool, and return the result as JSON text."""
    tool = TOOLS.get(name)
    if tool is None:
        logger.warning("tool_unknown", extra={"extra_fields": {"tool": name}})
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        args = tool.args_model.model_validate_json(arguments_json)
    except ValidationError as error:
        logger.warning(
            "tool_invalid_arguments",
            extra={"extra_fields": {"tool": name, "error_count": error.error_count()}},
        )
        problems = [issue["msg"] for issue in error.errors()]
        return json.dumps({"error": "Invalid arguments", "problems": problems})

    result = tool.function(args)
    logger.info(
        "tool_called",
        extra={"extra_fields": {"tool": name, "found": result.get("found")}},
    )
    return json.dumps(result)