# Day 8 — Bug-fix agent, project day 3: our own Python MCP client
**Date:** Sat 28 Nov 2026  **Status:** Green

## Goal
Replace the Inspector with our own code: connect to both official MCP servers from Python,
read a Bug cleanly, and enforce a tool policy (safety layer 2).

## What I built
- `app/agent/tickets.py` — BugTicket, HTML → text, untrusted-marker unwrapping, BE/FE area
- `app/agent/policy.py` — deny-by-default allowlist with argument rules
- `app/agent/servers.py` — how to start each server (least privilege per phase)
- `app/agent/hub.py` — McpHub: both servers, visible tools, policy-checked calls, metadata logs
- New settings in `app/config.py` + `.env.example`
- Scripts: mcp_github_smoke, mcp_ado_smoke, agent_hub_smoke
- Tests: 64 passing (tickets, policy, hub with fake clients)

## Concepts I learned
- async/await, async with, anyio.run; why MCP clients are async
- MCP SDK v2 Client + StdioServerParameters; allow-listed child environment
- Protocol version negotiation (2026-07-28 vs 2025-11-25 fallback)
- Tool results are typed blocks: TextContent vs EmbeddedResource
- Tool errors come back as is_error=True, not exceptions
- Data minimization at the source (`fields`)
- Deny-by-default policies; checking arguments, not just tool names
- Why the agent must never edit tests
- AsyncExitStack; dependency injection; fake clients (test doubles)

## Results
| Check | Result |
|---|---|
| pytest | 64 passed |
| Tools visible to the LLM | 2 (get_file_contents, wit_work_item) |
| Real reads through the hub | Bug 14098 (~1.7 s), app/ listing (~1.1 s) |
| Forbidden calls | 5/5 blocked before reaching a server |

## Problems and findings
| Finding | Fix |
|---|---|
| File content missing from the result | Handle EmbeddedResource blocks |
| Full work item includes names/emails | Request only needed fields |
| app/ listing is 6.8K characters | Shrink tool results before the LLM (Day 9) |



## Next (Day 9, project day 4)
Analyze + locate: LLM reads the BugTicket, browses the repo through the hub, and names the
file and function that likely contain the bug.