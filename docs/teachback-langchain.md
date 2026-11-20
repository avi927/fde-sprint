# Teach-back: LangChain retrievers and runnables vs plain Python

**Presenter:** ?  **Date:** 2026-11-21  **Length:** ~10 minutes + questions

## 1. What LangChain is (1 min)
- Framework of standard interfaces + integrations for LLM apps; core = langchain-core
- Integrations in separate packages (e.g. langchain-postgres); LangGraph for agents

## 2. Runnables (2 min)
- One interface for every step: invoke / batch / stream / ainvoke
- Compose with |  →  chain = step_a | step_b | step_c
- Dict in a chain = parallel branches; RunnablePassthrough passes input through

## 3. Retrievers (2 min)
- Runnable: query → list[Document] (page_content + metadata)
- Two ways: vector_store.as_retriever() or subclass BaseRetriever (_get_relevant_documents)
- Demo: our hybrid+rerank search wrapped as KnowledgeBaseRetriever

## 4. Live demo (2 min)
- python -m scripts.langchain_teachback
- What the chain output lacks vs /ask: no JSON validation, no citation check,
  no retry, no IDK short-circuit, no dedupe/word budget, no timings/tokens.
- Real example: chain cited [returns-guide#2], which was NOT in the retrieved
  context (only #0, #1, #3, refund-sale-items#0) → hallucinated citation.
  /ask's check_answer() rejects unknown citations and retries.

## 5. Trade-offs (2 min)
- Gives: ?
- Costs: ?

## 6. Our decision (1 min)
- ?  (e.g. keep plain-Python core; use framework at the edges; retriever interface for later)

## Questions to ask the audience
- When would you choose LangChain for a customer project?
- What would break if LangChain changed an API we depend on?