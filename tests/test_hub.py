"""Unit tests for app/agent/hub.py with fake MCP clients (no servers started)."""

from types import SimpleNamespace

import anyio
import pytest
from mcp.types import TextContent

from app.agent.hub import McpHub, ToolCallError
from app.agent.policy import PolicyViolation

SETTINGS = SimpleNamespace(github_owner="me", github_repo="proj", github_base_branch="bug-playground")
REPO = {"owner": "me", "repo": "proj"}


class FakeClient:
    """Records calls and returns canned results, like an MCP Client would."""

    def __init__(self, tool_names: list[str], is_error: bool = False) -> None:
        self.tool_names = tool_names
        self.is_error = is_error
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        tools = [
            SimpleNamespace(name=name, description=f"{name} tool", input_schema={}, annotations=None)
            for name in self.tool_names
        ]
        return SimpleNamespace(tools=tools)

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        return SimpleNamespace(content=[TextContent(type="text", text="ok")], is_error=self.is_error)


def run(coro_fn):
    return anyio.run(coro_fn)


def test_only_allowed_tools_are_visible():
    github = FakeClient(["get_file_contents", "list_commits", "merge_pull_request"])
    ado = FakeClient(["wit_work_item", "wit_work_item_write"])

    async def scenario():
        async with McpHub(SETTINGS, clients={"github": github, "ado": ado}) as hub:
            return {(tool.server, tool.name) for tool in await hub.visible_tools()}

    assert run(scenario) == {("github", "get_file_contents"), ("ado", "wit_work_item")}


def test_blocked_call_never_reaches_the_server():
    github = FakeClient(["get_file_contents"])

    async def scenario():
        async with McpHub(SETTINGS, clients={"github": github}) as hub:
            await hub.call("github", "list_commits", REPO)

    with pytest.raises(PolicyViolation):
        run(scenario)
    assert github.calls == []


def test_allowed_call_returns_text():
    github = FakeClient(["get_file_contents"])

    async def scenario():
        async with McpHub(SETTINGS, clients={"github": github}) as hub:
            return await hub.call("github", "get_file_contents", {**REPO, "path": "app/rag.py"})

    assert run(scenario) == "ok"
    assert github.calls == [("get_file_contents", {**REPO, "path": "app/rag.py"})]


def test_tool_error_becomes_exception():
    github = FakeClient(["get_file_contents"], is_error=True)

    async def scenario():
        async with McpHub(SETTINGS, clients={"github": github}) as hub:
            await hub.call("github", "get_file_contents", {**REPO, "path": "missing.py"})

    with pytest.raises(ToolCallError):
        run(scenario)