# Day 7 — Bug-fix agent, project day 2: practice environment
**Date:** Fri 27 Nov 2026  **Status:** Green

## Goal
Build a realistic practice setup: unit tests, planted bugs on a separate branch,
and Bug tickets the agent will read.

## What I did
- pytest setup (`pytest.ini`, `tests/`), moved tests out of `app/`
- 30 unit tests on main: chunking, RRF, context (sanitize, dedupe, budget),
  RAG answer checks, code-fence cleaning — all passing
- Fixed requirements.txt encoding (UTF-16 → ASCII), ignored `.pytest_cache/`
- Created `bug-playground` branch and planted 6 bugs → 8 failing tests
- Created 6 symptom-only Bug tickets (14098–14103) in the sandbox project
- Saved the answer key `evals/bugfix_cases.json` on main only

## Concepts I learned
- Unit tests vs evals: exact checks of plain code vs scored LLM behaviour
- assert, pytest.raises, pytest.approx, helper functions, reading a failure diff
- Boundary bugs (> vs >=, start=0 vs 1) and why tests target boundaries
- Branches as isolated copies: same folder, different code per branch
- Keeping the eval fair: no answer key in the agent's view

## Results
| Branch | pytest |
|---|---|
| main | 30 passed |
| bug-playground | 8 failed, 22 passed |


## Next (Day 8, project day 3)
Python MCP client: connect to both servers from code, tool allowlists, read a Bug ticket
and clean its HTML repro steps.