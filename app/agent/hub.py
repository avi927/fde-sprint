"""One doorway to both MCP servers: visible tools are filtered, every call is policy-checked."""

import logging
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mcp import Client
from mcp.types import EmbeddedResource, TextContent, TextResourceContents

from app.agent.policy import RepoTarget, check_call, is_visible
from app.agent.servers import ado_server_params, github_server_params
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class ToolCallError(Exception):
    """Raised when a server ran the tool but reported an error (is_error=True)."""


@dataclass(frozen=True)
class AgentTool:
    """A tool the LLM is allowed to see."""

    server: str
    name: str
    description: str
    input_schema: dict[str, Any]
    read_only: bool | None


def text_of(result: Any) -> str:
    """Join the text of a tool result: plain text blocks and embedded text files."""
    parts: list[str] = []
    for block in result.content:
        if isinstance(block, TextContent):
            parts.append(block.text)
        elif isinstance(block, EmbeddedResource) and isinstance(block.resource, TextResourceContents):
            parts.append(block.resource.text)
    return "\n".join(parts)


def repo_target(settings: Settings) -> RepoTarget:
    if not settings.github_owner or not settings.github_repo:
        raise ValueError("GITHUB_OWNER and GITHUB_REPO must be set in .env")
    return RepoTarget(settings.github_owner, settings.github_repo, settings.github_base_branch)


class McpHub:
    """Starts both servers together (async with) and routes every call through the policy."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        writes_approved: bool = False,
        clients: dict[str, Any] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.writes_approved = writes_approved
        self.target = repo_target(self.settings)
        self._clients: dict[str, Any] = dict(clients or {})
        self._start_servers = clients is None  # tests pass fake clients instead
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> "McpHub":
        await self._stack.__aenter__()
        if self._start_servers:
            try:
                github = github_server_params(self.settings, allow_writes=self.writes_approved)
                self._clients["github"] = await self._stack.enter_async_context(Client(github))
                ado = ado_server_params(self.settings)
                self._clients["ado"] = await self._stack.enter_async_context(Client(ado))
            except BaseException:
                await self._stack.aclose()  # stop anything that already started
                raise
        return self

    async def __aexit__(self, *exc_info: object) -> bool | None:
        return await self._stack.__aexit__(*exc_info)

    async def visible_tools(self) -> list[AgentTool]:
        """Only the tools the policy allows - the LLM never sees the others."""
        tools: list[AgentTool] = []
        for server, client in self._clients.items():
            for tool in (await client.list_tools()).tools:
                if is_visible(server, tool.name):
                    read_only = tool.annotations.read_only_hint if tool.annotations else None
                    tools.append(
                        AgentTool(server, tool.name, tool.description or "", tool.input_schema, read_only)
                    )
        return tools

    async def call(self, server: str, tool: str, arguments: dict[str, Any]) -> str:
        """Policy check first (raises PolicyViolation), then the real call."""
        access = check_call(server, tool, arguments, self.target, writes_approved=self.writes_approved)

        start = time.perf_counter()
        result = await self._clients[server].call_tool(tool, arguments)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        text = text_of(result)

        logger.info(
            "mcp_tool_called",
            extra={
                "extra_fields": {
                    "server": server,
                    "tool": tool,
                    "access": access.value,
                    "is_error": result.is_error,
                    "latency_ms": latency_ms,
                    "result_chars": len(text),
                }
            },
        )
        if result.is_error:
            raise ToolCallError(f"{server}.{tool} failed: {text[:500]}")
        return text