"""Minimal LlamaIndex adapter for proofrag's callable runner."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI

CORPUS = Path(__file__).resolve().parents[1] / "docs-rag" / "corpus"


@lru_cache(maxsize=1)
def _query_engine():
    """Build the in-memory index once, then reuse it for each question."""
    documents = SimpleDirectoryReader(input_dir=str(CORPUS)).load_data()
    index = VectorStoreIndex.from_documents(
        documents,
        embed_model=OpenAIEmbedding(model="text-embedding-3-small"),
    )
    return index.as_query_engine(
        llm=OpenAI(model="gpt-4o-mini"),
        similarity_top_k=3,
    )


def answer(question: str) -> dict[str, object]:
    """Answer a question and return the source nodes in proofrag's format."""
    response = _query_engine().query(question)
    return {
        "answer": str(response),
        "retrieved_contexts": [source.node.get_content() for source in response.source_nodes],
    }
