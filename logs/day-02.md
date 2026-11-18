# Day 2 — Wed 18 Nov 2026 (finished Thu 19 Nov)

**Focus:** Prompt engineering, prompt management, structured outputs, evals, safety, tool calling
**Status:** 🟡 Amber — Must items done one day late (Day 2 is the plan's heaviest day);
streaming and cost-in-$ moved to backlog.

---

## What I built

- **Prompt library:** `prompts/` folder with versioned prompt files
  - `triage_v1.md` (naive) → `v2` (role + allowed values + format rules)
    → `v3` (+ business rules, steps, 3 few-shot examples) → `v4` (+ partial-outage rule)
  - `chat_v1.md` (no-invention rules for /chat)
  - `assistant_v1.md` (tool-using support assistant)
- **Prompt loader:** `app/prompts.py` (`load_prompt(name, version)`, cached, UTF-8)
- **Structured output:** `POST /triage`
  - `TriageResult` schema (Literal values, `extra="forbid"`)
  - Validate-and-retry with Pydantic error feedback (max 3 attempts)
  - Markdown code-fence stripping in code before any retry
- **Central exception handlers** in `main.py` (shared by all endpoints)
- **First eval:** `evals/triage_cases.json` (golden dataset, now 14 cases)
  + `scripts/run_eval.py` (per-field scoring, mistakes list, saved results)
- **Safety:** attack tests, injection eval cases, `<ticket>` tag stripping, `docs/safety-notes.md`
- **Tool calling:** `app/tools.py` (`get_order_status` + fake order DB, tool registry,
  argument validation), `app/assistant.py` (tool loop, max 5 steps), `POST /assistant`
- **Refactor:** shared `get_openai_client()` in `llm_clients.py`

---

## What broke and how I fixed it

1. **v1 output unusable by code**
   - Invented categories ("Order Modification", "Shipping / Delivery", "Login Issue"),
     mixed casing ("Medium"/"medium"), JSON wrapped in ```json fences, and different
     answers for the same ticket on reruns.
   - Fix: allowed values + format rules (v2), business rules + examples (v3).

2. **v2 had perfect JSON but wrong decisions**
   - Guessed priorities (double charge → "urgent", polite refund → "medium") and sent
     simple questions to a human.
   - Fix: explicit priority and needs_human rules in v3. Lesson: validation can't catch
     wrong decisions — only evals can.

3. **Rule gap: "premium logout" ticket**
   - v3 answered urgent → urgent → medium across runs (unstable).
   - Cause: no rule for "paid feature partly broken".
   - Fix: v4 adds one rule; added 2 boundary cases to avoid overfitting.

4. **Bug in my own eval dataset**
   - A placeholder (`true_or_false_placeholder`) was left in `needs_human`, so no model
     could pass that case.
   - Fix: accepted `[true, false]` and recorded an open requirement question.
   - Lesson: evals have bugs too — check the test before blaming the model.

5. **v4 looked slower than v3 (2,818 ms / 1,560 ms vs ~900–1,000 ms)**
   - Its prompt is only ~23 tokens longer, so the prompt can't explain it.
   - Hypothesis: free-tier rate limiting (v4 always ran second, after ~8,500 tokens of v3
     calls) → SDK retries counted inside the latency.
   - Test: `run_eval v4 v3` (reversed order) → result: ?

6. **/chat invented a full refund policy** ("our policy: 30 days, 5–7 business days,
   prepaid label") — an ungrounded answer with liability risk.
   - Fix (prompt-level): `chat_v1.md` states what the model has no access to and forbids
     inventing policies/orders. Result after fix: ?
   - Real fix: RAG grounding (Day 4).

7. **v1 obeyed an indirect prompt injection** (hidden "SYSTEM NOTE TO AI" → other/low/false)
   - v2–v4 resisted thanks to the delimiter + "treat as data" rule.

8. **Delimiter escape risk** (`</ticket>` inside a ticket)
   - Fix: strip `<ticket>` tags from input in code (`_sanitize_ticket`, regex, case-insensitive).
   - Eval before fix: ? / after fix: ?

---

## What I learned

### Prompt engineering
- A prompt is a program in English; the model only knows what's in the request.
- **System prompt** = trusted developer rules; **user message** = untrusted input.
- Untrusted data goes inside **delimiters** (`<ticket>…</ticket>`) with a "treat as data" rule.
- Techniques: role, clear task, **allowed values**, output format, **business rules**,
  steps, delimiters, **few-shot examples** (showing beats telling).
- Clear rules turn **random answers into consistent ones**.
- Better prompts cost more input tokens (v3 ≈ 5.5× v1), but **output tokens drive latency**
  and a bad prompt can cost more overall because of retries.
- Reasoning models spend hidden output tokens; "work through these steps silently" keeps
  reasoning out of the JSON.

### Prompt management
- Prompts are behavior, like code: versioned files, never edit old versions,
  compare, roll back, review.
- **Promote by evidence:** a prompt becomes the default only when the eval proves it.

### Structured output and validation
- **LLM output is untrusted input** — always validate it.
- The prompt and the schema must match (allowed values in both).
- `extra="forbid"` catches the model not following the format.
- **Validate-and-retry:** Pydantic's error messages are good feedback; limit retries.
- **Cheap fix first:** fix in code (strip fences) before paying for a retry.
- Validation checks the format, not whether the decision is right.

### Evals
- Testing checks the code works; **evals measure answer quality as a score**.
- **Golden dataset:** test cases + correct answers + a note explaining each answer.
  Labels are **business decisions**, owned with the customer.
- Allow **several acceptable values** for subjective fields.
- **Per-field scores** show *what* to fix.
- Mistakes are one of three kinds: **rule gap**, **model error**, **label disagreement**.
- **Change one thing, then re-run everything** (catch regressions).
- Add **boundary cases** on both sides of a new rule to avoid **overfitting**.
- One run is noisy; **averages hide outliers** (use p50/p95 later).
- Be suspicious of 100% (sentiment) — the test may be too easy.
- Some errors are worse than others (missing a needed human vs a false alarm).

### Safety
- Four failures: **hallucination, ungrounded answers, direct injection, indirect injection**.
- Indirect injection matters most for RAG (Day 4) and MCP/agents (Day 6–7).
- **Defense in depth:** delimiters + rules, tag stripping in code, strict output schema
  (limits the **blast radius**), input limits, attack cases in evals, no secrets in prompts.
- **Deterministic defenses (code) beat polite requests (prompt).**
- Models may refuse to reveal their system prompt (built-in training), but it's not guaranteed.
- Companies can be held liable for what their chatbot invents (Air Canada, 2024).

### Tool calling
- The **model never runs code**; it asks, and **my code decides** and runs the tool.
- Loop: question + tool menu → tool call request → run tool → send result → final answer.
- The model has no memory: every call sends the **whole conversation**
  (`system`, `user`, `assistant` with `tool_calls`, `tool` with `tool_call_id`).
- **Tool arguments are untrusted** — validate them (`pattern=r"^\d{4}$"`).
- Return tool errors **as data** so the model can recover.
- **Loop limit** (`MAX_STEPS = 5`) prevents endless calls and runaway cost.
- Pydantic generates the tool's JSON schema → one source of truth.
- Read-only tools are low risk; write tools need limits and human approval.
- MCP = tools in a separate server with a standard protocol (my Day 6 track).

### Python
- `pathlib.Path`, `__file__`, `.parent`, `/` to join paths; `encoding="utf-8"` on Windows
- Default parameters (backward-compatible changes), keyword arguments, `sys.argv`
- `json.loads` / `json.dumps`, `time.sleep`, `re.sub` and raw strings `r"..."`
- `range`, `+=`, `continue`, slicing, `isinstance`, `.get()`, `**dict` unpacking
- List and dictionary comprehensions
- f-string format specs: `:<8`, `:>9.0%`, `:.2f`, `!r`
- Pydantic: `model_validate_json`, `ValidationError.errors()`, `model_dump`, `model_json_schema`
- Dataclasses: `field(default_factory=list)`; type hints `Callable`, `type[...]`, `Any`
- FastAPI: exception handlers, stacked decorators, `JSONResponse`, nested response models

### Engineering practices
- **DRY:** central error handlers, shared `get_openai_client()`, `_error_response` helper
- **Refactor → regression test** the old behavior
- Business logic in its own module (`triage.py`) so the API **and** the eval reuse it
- Controlled experiments: change only one thing (e.g. run order) to find a cause

---

## Checklist status (from the plan)

- [x] 3 prompt versions compared (v1–v4)
- [x] Prompt library folder created
- [x] JSON-schema endpoint validated (`/triage`)
- [ ] Streaming works → **moved to backlog** (Day 9)
- [ ] One tool call demonstrated ← ? (code done, tests pending)
- [~] Token usage logged ✅ / cost in $ → **moved to backlog** (Day 13)
- [x] Injection examples noted (`docs/safety-notes.md`)
- [x] Decision log entries

---

## Measurements

### Eval run 1 — 10 cases (`triage_20261118-190951.json`)

| Version | Perfect | Category | Priority | Sentiment | needs_human | Avg attempts | Input tokens | Avg ms |
|---|---|---|---|---|---|---|---|---|
| v1 | 4/10 | 90% | 40% | 100% | 70% | 1.90 | 3,022 | 1,647 |
| v2 | 6/10 | 100% | 70% | 100% | 80% | 1.00 | 2,701 | 851 |
| v3 | 9/10 | 100% | 90% | 100% | 100% | 1.00 | 7,081 | 1,179 |

### Eval run 2 — 12 cases, dataset bug fixed (`triage_20261118-200913.json`)

| Version | Perfect | Priority | needs_human | Avg ms |
|---|---|---|---|---|
| v3 | 10/12 | 83% | 100% | 899 |
| v4 | **12/12** | **100%** | 100% | 1,560 |

### Eval run 3 — 14 cases with injection cases (v4)

| Run | Perfect | Notes |
|---|---|---|
| Before `_sanitize_ticket` | ?/14 | ? |
| After `_sanitize_ticket` | ?/14 | ? |

### Tool calling (`/assistant`)

| Test | tools_used | steps | Result |
|---|---|---|---|
| Order #4521 status | ? | ? | ? |
| Order 9999 (not found) | ? | ? | ? |
| No order number | ? | ? | ? |
| Refund 7781 | ? | ? | ? |
| Refund policy | ? | ? | ? |
| Injection in order number | ? | ? | ? |

---

## Evidence

- Prompt files in Git: `prompts/triage_v1.md` … `triage_v4.md`, `chat_v1.md`, `assistant_v1.md`
- Eval results: `evals/results/triage_20261118-190951.json`,
  `triage_20261118-195920.json`, `triage_20261118-200913.json`, ?
- Swagger screenshots: `/triage` v3 (attempts 1), v1 (attempts 2), 422, `/assistant` ?
- `docs/safety-notes.md`, `docs/decision-log.md`
- Commit links: ?

---

## Open items / blockers

- Report: injection eval before/after the fix; D1/D2 after `chat_v1`; `/assistant` tests;
  regression check (`/chat` 200 + 503, `/triage` 200 with v4)
- Confirm the latency hypothesis: `python -m scripts.run_eval v4 v3`
- **Open question for the customer:** should a paying customer who cannot use the product
  at all always reach a human? (then add a rule in v5)
- Backlog: streaming endpoint (Day 9), cost in $ per request (Day 13)
- Anthropic API key still missing (carried over from Day 1)

---

## Tomorrow — Day 3 (planned Thu 19 Nov, starting one day late)

- Embeddings: what they are, cosine vs dot product, dimensions, choosing a model
- Embed 20–50 documents and store them in PostgreSQL with pgvector
  (tables, indexes, JSONB metadata, migrations)
- Semantic search endpoint returning top-k, with metadata filters
- Compare keyword vs semantic search on 10 queries
- Demo 1 + progress check (Green / Amber / Red)