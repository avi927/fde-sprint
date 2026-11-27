"""Day 8: first Python MCP call - list GitHub tools and read a file from bug-playground."""

import anyio
from mcp import Client, StdioServerParameters
from mcp.types import EmbeddedResource, TextContent, TextResourceContents

from app.config import get_settings

GITHUB_IMAGE = "ghcr.io/github/github-mcp-server"


def github_server_params() -> StdioServerParameters:
    """How to start the official GitHub MCP server: read-only, repo tools only."""
    settings = get_settings()
    if settings.github_personal_access_token is None:
        raise SystemExit("GITHUB_PERSONAL_ACCESS_TOKEN is not set in .env")
    return StdioServerParameters(
        command="docker",
        args=[
            "run", "-i", "--rm",
            "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
            "-e", "GITHUB_READ_ONLY",
            "-e", "GITHUB_TOOLSETS",
            GITHUB_IMAGE,
        ],
        env={
            "GITHUB_PERSONAL_ACCESS_TOKEN": settings.github_personal_access_token.get_secret_value(),
            "GITHUB_READ_ONLY": "1",
            "GITHUB_TOOLSETS": "repos",
        },
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
    async with Client(github_server_params()) as client:
        print("protocol version:", client.protocol_version)

        tools = (await client.list_tools()).tools
        print(f"{len(tools)} tools:")
        for tool in tools:
            read_only = tool.annotations.read_only_hint if tool.annotations else None
            print(f"  {tool.name:<34} read_only={read_only}")

        result = await client.call_tool(
            "get_file_contents",
            {
                "owner": settings.github_owner,
                "repo": settings.github_repo,
                "path": "app/text_utils.py",
                "ref": f"refs/heads/{settings.github_base_branch}",
            },
        )
        if result.is_error:
            print("TOOL ERROR:", text_of(result))
            return
        print("blocks:", [type(block).__name__ for block in result.content])
        print("\n--- app/text_utils.py on", settings.github_base_branch, "---")
        print(text_of(result))


if __name__ == "__main__":
    anyio.run(main)