"""Teach-back: the same RAG pipeline expressed with LangChain retrievers and runnables."""

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from app.context import sanitize
from app.llm_clients import call_openai
from app.logging_config import setup_logging
from app.prompts import load_prompt
from app.search import search_chunks


class KnowledgeBaseRetriever(BaseRetriever):
    """Our own hybrid + rerank search, exposed through LangChain's retriever interface."""

    top_k: int = 5
    mode: str = "hybrid"
    rerank: bool = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        outcome = search_chunks(query, top_k=self.top_k, mode=self.mode, rerank=self.rerank)
        return [
            Document(
                page_content=hit.content,
                metadata={"source_id": hit.source_id, "title": hit.title, "score": hit.score},
            )
            for hit in outcome.hits
        ]


def format_context(docs: list[Document]) -> str:
    """Documents -> the labelled <context> block our rag_v1 prompt expects."""
    blocks = [
        f'<source id="{doc.metadata["source_id"]}" title="{doc.metadata["title"]}">\n'
        f"{sanitize(doc.page_content)}\n</source>"
        for doc in docs
    ]
    return "<context>\n" + "\n\n".join(blocks) + "\n</context>"


def build_message(inputs: dict[str, str]) -> str:
    """{'context': ..., 'question': ...} -> the user message."""
    return f"{inputs['context']}\n\n<question>\n{sanitize(inputs['question'])}\n</question>"


def generate(message: str) -> str:
    """Call our LLM client with the RAG system prompt; return the raw model text."""
    return call_openai(message, system_prompt=load_prompt("rag", "v1")).text


def main() -> None:
    setup_logging("WARNING")
    retriever = KnowledgeBaseRetriever()

    # 1. A retriever is a runnable: .invoke(query) -> list[Document]
    question = "Can I return opened headphones?"
    docs = retriever.invoke(question)
    print("Retriever output:")
    for doc in docs:
        print(f"  {doc.metadata['source_id']:<28} score={doc.metadata['score']}")

    # 2. Compose a chain with | (LCEL)
    chain = (
        {
            "context": retriever | RunnableLambda(format_context),
            "question": RunnablePassthrough(),
        }
        | RunnableLambda(build_message)
        | RunnableLambda(generate)
    )

    print("\nChain output (raw model text):")
    print(chain.invoke(question))


if __name__ == "__main__":
    main()