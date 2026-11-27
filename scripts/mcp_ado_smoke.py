"""Day 8: read a Bug from Azure Boards through the official Azure DevOps MCP server (read-only)."""

import json

import anyio
from mcp import Client, StdioServerParameters
from mcp.types import EmbeddedResource, TextContent, TextResourceContents

from app.config import get_settings
from app.agent.tickets import BUG_FIELDS, parse_bug

BUG_ID = 14098


def ado_server_params() -> StdioServerParameters:
    """How to start the official Azure DevOps MCP server: projects + work items only."""
    settings = get_settings()
    if settings.ado_mcp_auth_token is None or settings.ado_org is None:
        raise SystemExit("ADO_MCP_AUTH_TOKEN and ADO_ORG must be set in .env")
    return StdioServerParameters(
        command="npx",
        args=[
            "-y", "@azure-devops/mcp", settings.ado_org,
            "-d", "core", "work-items",
            "--authentication", "envvar",
        ],
        env={"ADO_MCP_AUTH_TOKEN": settings.ado_mcp_auth_token.get_secret_value()},
    )


def text_of(result) -> str:
    """Join the text of a tool result: plain text blocks and embedded text files."""
    parts: list[str] = []
    for block in result.content:
        if isinstance(block, TextContent):
            parts.append(block.text)
        elif isinstance(block, EmbeddedResource) and isinstance(block.resource, TextResourceContents):
            parts.append(block.resource.text)
    return "\n".join(parts)

async def main() -> None:
    settings = get_settings()
    async with Client(ado_server_params()) as client:
        print("protocol version:", client.protocol_version)
        result = await client.call_tool(
            "wit_work_item",
            {"action": "get", "project": settings.ado_project, "id": BUG_ID, "fields": BUG_FIELDS},
        )
        if result.is_error:
            print("TOOL ERROR:", text_of(result))
            return
        ticket = parse_bug(text_of(result))
        print(ticket.model_dump_json(indent=2))


if __name__ == "__main__":
    anyio.run(main)