"""Day 8: both servers through the hub - visible tools, a real read from each, and blocked calls."""

import anyio

from app.agent.hub import McpHub
from app.agent.policy import PolicyViolation
from app.agent.tickets import BUG_FIELDS, parse_bug
from app.config import get_settings
from app.logging_config import setup_logging

BUG_ID = 14098


async def main() -> None:
    setup_logging("INFO")
    settings = get_settings()
    repo = {"owner": settings.github_owner, "repo": settings.github_repo}

    async with McpHub() as hub:
        print("\nTools the LLM will see:")
        for tool in await hub.visible_tools():
            print(f"  {tool.server}.{tool.name:<22} read_only={tool.read_only}")

        raw = await hub.call(
            "ado",
            "wit_work_item",
            {"action": "get", "project": settings.ado_project, "id": BUG_ID, "fields": BUG_FIELDS},
        )
        ticket = parse_bug(raw)
        print(f"\nBug {ticket.id} [{ticket.area}]: {ticket.title}")

        listing = await hub.call(
            "github",
            "get_file_contents",
            {**repo, "path": "app/", "ref": f"refs/heads/{settings.github_base_branch}"},
        )
        print(f"Read app/ listing from {settings.github_base_branch}: {len(listing)} characters")

        print("\nCalls that must be blocked:")
        blocked = [
            ("github", "list_commits", repo),
            ("github", "merge_pull_request", {**repo, "pullNumber": 1}),
            ("github", "create_branch", {**repo, "branch": "bugfix/test", "from_branch": "bug-playground"}),
            ("ado", "wit_work_item", {"action": "my"}),
            ("ado", "wit_work_item_comment_write", {"workItemId": BUG_ID, "comment": "x"}),
        ]
        for server, tool, arguments in blocked:
            try:
                await hub.call(server, tool, arguments)
                print(f"  !! {server}.{tool} was NOT blocked")
            except PolicyViolation as error:
                print(f"  BLOCKED {server}.{tool}: {error}")


if __name__ == "__main__":
    anyio.run(main)