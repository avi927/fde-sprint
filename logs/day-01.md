# Day 1 — Tue 17 Nov 2026

**Focus:** Kickoff, environment setup, FastAPI, LLM API basics
**Status:** 🟢 Green (Anthropic call pending an API key)

---

## What I built

- A FastAPI project with a clean package structure (`app/`, `scripts/`, `docs/`, `logs/`)
- Typed config loaded from `.env` with Pydantic Settings (secrets hidden with `SecretStr`)
- Structured JSON logging for the whole app
- An LLM client layer (`app/llm_clients.py`) that calls:
  - the OpenAI SDK, pointed at Groq (`openai/gpt-oss-120b`)
  - the Anthropic SDK (code ready, waiting for an API key)
- A common `LLMResult` dataclass, so every provider returns the same shape
- A test script: `python -m scripts.try_llm`
- `GET /health`: liveness check plus which providers are configured
- `POST /chat`: validated request, provider choice, timeout, retries and clean error codes
- Tested everything in Swagger UI

---

## What broke and how I fixed it

1. **`python` opened the Microsoft Store**
   - Cause: Windows has a fake `python` shortcut that points to the Store.
   - Fix: use the `py` launcher (`py -3.14 -m venv .venv`). Inside an activated venv, `python` works.

2. **Two Python versions installed (3.15 and 3.14)**
   - Chose 3.14 because 3.15 is very new and some libraries may not support it yet.

3. **PowerShell blocked the venv activation script**
   - Fix: allow local scripts with `Set-ExecutionPolicy` (VS Code now activates the venv automatically).

4. **`__pycache__` showed up in Git**
   - Cause: `.gitignore` was empty because the file was never saved.
   - Fix: saved it, then ran `git add .gitignore` again, because staging takes a snapshot at that moment.
   - `git rm --cached` failed because the files were untracked, not staged.
   - Also learned: Python 3.13+ venvs ignore themselves with their own `.gitignore`.

5. **Anthropic returned 401 "Invalid bearer token"**
   - First guess: an environment variable overriding `.env`. Checked, and that was ruled out.
   - Real cause: `.env` still had the placeholder text, not a real key (found by printing the first 10 characters and the length).
   - Fix for now: left `ANTHROPIC_API_KEY` empty, so the app gives a clear "not configured" error (503).

6. **Confusion: why `provider: "openai"` when I'm using Groq?**
   - "openai" means the OpenAI SDK and API format; `OPENAI_BASE_URL` decides which server it calls.
   - Kept the name as it is and documented it in the decision log.

---

## What I learned

### The FDE role
- An FDE builds and ships solutions inside the customer's real environment, and owns the business outcome, not just the ticket.
- Half the job is customer-facing: discovery, explaining trade-offs, writing clear docs.
- Writing (comparisons, decision logs, READMEs) is part of the deliverable, not extra.

### Python and tooling
- **Virtual environment (`.venv`):** a private set of libraries for each project, like `node_modules`. Activate it in every new terminal.
- **pip** installs packages; `pip freeze > requirements.txt` pins exact versions so teammates get the same setup.
- **Packages:** an `__init__.py` file makes a folder importable (`from app.config import ...`).
- **`python -m scripts.try_llm`** runs a file as a module from the project root, so imports work.
- **`if __name__ == "__main__":`** runs code only when the file is run directly.
- Python basics: indentation instead of braces, type hints, `None`, f-strings, dictionaries, lists, tuples, `try`/`except`, `raise`, classes, inheritance, `self`, decorators (`@`).
- **Dataclass** (`@dataclass(frozen=True)`): a simple container for internal data. **Pydantic** validates data coming from outside (`.env`, HTTP requests).

### Git
- `.gitignore` must exist **before** the first `git add`.
- Staging is a snapshot: edit a file after `git add` and you must add it again.
- `git rm --cached` removes a file from Git without deleting it from disk.
- Small, focused commits with clear messages; `git push -u` once, then just `git push`.

### Config and secrets
- Code stays the same everywhere; configuration comes from the environment (the 12-Factor idea).
- `.env` holds real secrets and is never committed; `.env.example` lists the names and is committed.
- `SecretStr` prints `**********`, which protects keys from leaking into logs.
- `Literal[...]` makes the app **fail fast** at startup on a bad config value.
- Priority order: **real environment variables > `.env` > defaults in code.**
- `@lru_cache` reads settings once; changing `.env` needs a server **restart**.
- "Configured" doesn't mean "valid": only a real call proves a key works.

### Logging
- Logger, handler, formatter: what to log, where it goes, what it looks like.
- JSON logs can be searched and filtered (e.g. in CloudWatch); plain text can't.
- Log levels: DEBUG < INFO < WARNING < ERROR, controlled from config.
- Log **metadata** (provider, tokens, latency), **never** prompts, answers or secrets, because they may contain customer data.
- Use short event names (`llm_call_completed`) instead of sentences.

### LLM APIs
- An LLM call is just an HTTP request; the SDK is a wrapper around it.
- Messages have roles: **system** (how to behave) and **user** (the question).
- **Tokens = cost.** You pay for input and output tokens, and even a short prompt carries fixed overhead (~99 input tokens).
- **Reasoning models** spend hidden "thinking" tokens; set the output limit too low and the answer can come back empty.
- LLMs are **non-deterministic**: same question, different latency and wording.
- **OpenAI-compatible APIs:** Groq copies OpenAI's request and response format, so the OpenAI SDK works with Groq by changing only `base_url`, key and model.
- **Adapter pattern:** wrap every provider in one shape (`LLMResult`), so switching providers is a config change.
- Always set a **timeout**; the SDKs **retry** temporary failures automatically (`max_retries`).
- Free API options in 2026: Groq has a free tier, Anthropic gives small starter credits, OpenAI has no free tier.

### FastAPI
- Swagger UI (`/docs`) is generated automatically from your code and type hints.
- Pydantic `BaseModel` validates request bodies; bad input gets an automatic **422** before my code runs.
- `Field(min_length, max_length)` protects against empty and oversized input (cost and security).
- A separate **public** response model (`ChatResponse`) and **internal** model (`LLMResult`): an API contract.
- Use `def` (not `async def`) with blocking SDKs; FastAPI runs it in a worker thread.

### Error handling
- Translate provider errors into clear HTTP codes:
  - **422** bad input, **429** rate limited, **502** provider error, **503** not configured, **504** timeout.
- Don't pass the provider's 401 through: it's *our* key, so it's a 502 for the client.
- `except` order: **specific errors first, general last.**
- `raise ... from error` keeps the original cause for debugging.
- Detailed info goes in **logs**; short, safe messages go to the **client**. Never reveal secret names.
- Custom exceptions (`ProviderNotConfiguredError`) make errors clear and catchable.

### Debugging habits
- Read the error message carefully ("bearer token" was a clue).
- Form a guess, test it cheaply, rule it out, move on.
- Check safely: print a key's first characters and length, never the whole key.

---

## Checklist status

- [x] Repo created and pushed to GitHub
- [x] API keys in `.env`, not in Git
- [x] Spending limit: N/A (Groq free tier, no billing)
- [ ] Provider comparison written ← ?
- [x] `/chat` endpoint works (Test 1: 200 OK)
- [ ] Error tests passed (422 / 422 / 503 / 504) ← ?
- [x] Typed project structure with logging
- [~] Both provider SDKs called: OpenAI SDK ✅, Anthropic SDK code ready (no key yet)
- [x] Daily log written

---

## Measurements

| Run | Provider / model | Input tokens | Output tokens | Latency |
|---|---|---|---|---|
| Script | Groq / gpt-oss-120b | 99 | 109 | 959.9 ms |
| Swagger | Groq / gpt-oss-120b | 98 | 78 | 881.7 ms |

---

## Evidence

- Commit link: ?
- Swagger screenshots: ? (200 response, and 503 for anthropic)
- Provider comparison: `docs/provider-comparison.md`

---

## Open items / blockers

- Get an Anthropic API key to complete "both SDKs called"
- Finish `docs/provider-comparison.md` and the decision log entries if not done

---

## Tomorrow (Day 2 — Wed 18 Nov)

- System vs. user prompts, few-shot examples
- Prompt files stored in Git (versioned), with 10 test inputs to compare versions
- Structured output with JSON schema and Pydantic validation, plus retries
- Streaming responses and tool calling basics
- Prompt injection and hallucination examples