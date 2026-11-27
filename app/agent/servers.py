"""How to start the two official MCP servers (stdio child processes)."""

from mcp import StdioServerParameters

from app.config import Settings

GITHUB_IMAGE = "ghcr.io/github/github-mcp-server"


class ServerConfigError(Exception):
    """Raised when a required setting for an MCP server is missing."""


def github_server_params(settings: Settings, *, allow_writes: bool) -> StdioServerParameters:
    """GitHub server: read-only unless writes are approved; merge is always hidden."""
    if settings.github_personal_access_token is None:
        raise ServerConfigError("GITHUB_PERSONAL_ACCESS_TOKEN is not set in .env")

    env = {
        "GITHUB_PERSONAL_ACCESS_TOKEN": settings.github_personal_access_token.get_secret_value(),
        "GITHUB_TOOLSETS": "repos,pull_requests" if allow_writes else "repos",
        "GITHUB_EXCLUDE_TOOLS": "merge_pull_request",
    }
    if not allow_writes:
        env["GITHUB_READ_ONLY"] = "1"

    args = ["run", "-i", "--rm"]
    for name in env:
        args += ["-e", name]  # value comes from env=, never from the command line
    args.append(GITHUB_IMAGE)
    return StdioServerParameters(command="docker", args=args, env=env)


def ado_server_params(settings: Settings) -> StdioServerParameters:
    """Azure DevOps server: projects + work items only, token from an environment variable."""
    if settings.ado_mcp_auth_token is None or settings.ado_org is None:
        raise ServerConfigError("ADO_MCP_AUTH_TOKEN and ADO_ORG must be set in .env")
    return StdioServerParameters(
        command="npx",
        args=[
            "-y", "@azure-devops/mcp", settings.ado_org,
            "-d", "core", "work-items",
            "--authentication", "envvar",
        ],
        env={"ADO_MCP_AUTH_TOKEN": settings.ado_mcp_auth_token.get_secret_value()},
    )