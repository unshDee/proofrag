"""Offline tests for golden set generation."""

from typing import cast

from proofrag.goldenset import generate
from proofrag.llm import LLM


class _FakeLLM:
    def complete_json(self, system, prompt):
        return {"question": "What is documented?", "gold_answer": "The documented answer."}


def test_generate_preserves_context_metadata():
    chunks = [
        {
            "source": "docs/api.md",
            "chunk_id": "api.md::0",
            "chunk_index": 0,
            "char_count": 21,
            "extension": ".md",
            "text": "The documented answer.",
        }
    ]

    records = generate(chunks, n=1, llm=cast(LLM, _FakeLLM()))

    assert records[0]["sources"] == ["docs/api.md"]
    assert records[0]["gold_contexts"] == ["The documented answer."]
    assert records[0]["context_metadata"] == [
        {
            "source": "docs/api.md",
            "chunk_id": "api.md::0",
            "chunk_index": 0,
            "char_count": 21,
            "extension": ".md",
        }
    ]
