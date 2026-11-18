# Decision Log

## 2026-11-17 — Use Chat Completions API instead of OpenAI Responses API

- **Decision:** Call the OpenAI SDK's Chat Completions endpoint.
- **Why:** It is the format other providers copy (Groq, Gemini, Mistral), so the same
  code works across providers by changing only config (base URL, key, model).
- **Rejected:** Responses API — OpenAI recommends it for new projects and it has
  built-in tools, but other providers don't fully support it.
- **Revisit when:** We commit to OpenAI only, or need Responses-only features.

BUT:-
-> Groq for development (instead of paid OpenAI or Anthropic).
-> The provider name in the API stays "openai" (instead of "groq" or "openai_compatible"). Explain why you kept it, and what the trade-off is.
-> Error mapping: provider errors become 429/502/503/504 instead of passing the provider’s raw error to the client

DAY 2:-
-Decision: store prompts as versioned .md files in prompts/, loaded by app/prompts.py.
-Why: you can compare versions, roll back, review in pull requests, and non-developers can edit them.
-Rejected: prompts as strings inside Python code.

1-> Validate model output with Pydantic and retry with error feedback (max 3 attempts). 
Why: LLM output is untrusted and may break format even with good prompts; Pydantic’s error messages make good feedback. Rejected: trusting the output; unlimited retries (cost risk).

2-> Our own validation instead of relying only on provider JSON modes. 
Why: works with any provider, and acts as a safety net even when JSON mode is used. Revisit: add provider JSON mode as an extra layer if format failures are frequent.

3-> Central exception handlers instead of try/except in each endpoint. 
Why: DRY; consistent errors across all endpoints. Rejected: copying the except chain into /triage.