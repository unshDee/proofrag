"""Run the bundled corpus through a LangChain retrieval chain.

Install this example's optional dependencies and set ``OPENAI_API_KEY`` before
running it. From this directory, use ``proofrag run --goldenset goldenset.jsonl
--callable app:answer --out predictions.jsonl``.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

CORPUS = Path(__file__).resolve().parent.parent / "docs-rag" / "corpus"


@lru_cache(maxsize=1)
def _retrieval_chain() -> Any:
    """Build the in-memory index and retrieval chain once per process."""
    try:
        from langchain_classic.chains import create_retrieval_chain
        from langchain_classic.chains.combine_documents import create_stuff_documents_chain
        from langchain_core.documents import Document
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.vectorstores import InMemoryVectorStore
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise RuntimeError(
            "Install the example dependencies with `pip install -r requirements.txt`."
        ) from exc

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY before running the LangChain example.")

    documents = [
        Document(page_content=path.read_text(encoding="utf-8"), metadata={"source": path.name})
        for path in sorted(CORPUS.glob("*.md"))
    ]
    if not documents:
        raise RuntimeError(f"No Markdown documents found in {CORPUS}.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
    chunks = splitter.split_documents(documents)
    embeddings = OpenAIEmbeddings()
    store = InMemoryVectorStore.from_documents(chunks, embeddings)
    retriever = store.as_retriever(search_kwargs={"k": 3})

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Answer using only the retrieved context. If the context does not "
                "contain the answer, say you do not have enough information.\n\n"
                "Context:\n{context}",
            ),
            ("human", "{input}"),
        ]
    )
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    answer_chain = create_stuff_documents_chain(ChatOpenAI(model=model, temperature=0), prompt)
    return create_retrieval_chain(retriever, answer_chain)


def answer(question: str) -> dict[str, Any]:
    """Return a proofrag-compatible answer and the retrieved document texts."""
    result = _retrieval_chain().invoke({"input": question})
    return {
        "answer": result["answer"],
        "retrieved_contexts": [document.page_content for document in result["context"]],
    }
