# Day 6 — Bug-fix agent, project day 1: MCP fundamentals + smoke tests
**Date:** Wed 25 – Fri 27 Nov 2026  **Status:** Green

## Goal
Choose the Week 2 project, learn MCP fundamentals, and prove that both official MCP
servers (GitHub + Azure DevOps) and the LLM work on my machine before writing agent code.

## Project chosen
A bug-fix agent: reads a Bug ticket from Azure Boards (read-only), finds the related
code in GitHub, shows a plan + diff for my approval, then opens a DRAFT PR.
Never merges, never changes Azure Boards. Practice repo: fde-sprint (planted bugs).

## What I did
- Researched project options; chose official MCP servers instead of custom servers
- Tagged Week 1 state: `week1-rag-v0.8.0`
- Checked environment: Node v24.22.0, npm/npx 11.19.1, Docker 29.9.2, Python 3.14.9
- Created a fine-grained GitHub token (fde-sprint only, Contents + Pull requests, 30 days)
- Ran the official GitHub MCP server (Docker, stdio) in MCP Inspector
- Created an Azure DevOps sandbox project (Agile process, admin-approved) + sample Bug
- Created a read-only Azure DevOps token (Work Items Read + Project and Team Read, 30 days)
- Ran the official Azure DevOps MCP server (npx, stdio) in MCP Inspector
- Checked Groq still works (try_llm)

## Concepts I learned
- MCP = standard plug between AI apps and tools (N + M instead of N × M)
- Host (app with the LLM) / client (one connection per server) / server (offers tools, no LLM)
- Tools (model decides) / resources (app decides) / prompts (user decides)
- JSON-RPC: tools/list (discover), tools/call (run); result content + isError
- Transports: stdio (child process, stdout reserved for protocol, logs to stderr) vs Streamable HTTP
- Spec 2026-07-28 is stateless; real servers may use older versions (GitHub used 2025-11-25)
- Tool annotations: READ-ONLY, IDEMPOTENT, OPEN-WORLD
- Least-privilege tokens; passing secrets via environment variables, not command arguments
- Layered safety: hide tools (server) → allowlist (our code) → permissions (platform)
- Ticket text is untrusted input (the Azure DevOps server wraps it in random markers)

## Results
| Check | Result |
|---|---|
| GitHub server, read-only + repos toolset | 13 tools |
| Read file app/rag.py | ✅ (returned content + sha) |
| List folder app/ | ✅ 18 files (name, path, size, sha) |
| search_code (2 known terms) | ❌ 0 results, incomplete_results: true |
| Exclude merge_pull_request | 29 → 28 tools ✅ |
| Azure DevOps server, `-d core work-items` | 12 tools |
| Read Bug via wit_work_item (action: get) | ✅ title, state, priority, severity, repro steps |
| Add comment with read-only token | ✅ "Unauthorized" (write blocked) |
| Groq gpt-oss-120b | ✅ 200 OK, 99/120 tokens, ~967 ms |

## Problems and findings
| Finding | Cause | What we do |
|---|---|---|
| search_code returns nothing for my repo | GitHub code search not returning results for this repo | Browse folders + read files instead |
| "tag already exists" | Tag was created earlier | Checked it with git log; pushed it |
| Repro Steps are HTML | Azure DevOps stores rich text as HTML | Convert to plain text (Day 3) |
| Ticket responses include names, emails, IDs | Full work item payload | Extract only needed fields (Day 3) |
| Azure DevOps server shows write tools | Server has no read-only flag here | Read-only token + our allowlist |

## Key insight
?  (one or two sentences in your own words)

## Next (Day 7, project day 2)
Practice environment: `bug-playground` branch, pytest setup, planted bugs with failing
tests, and matching Bug tickets in the sandbox project.
