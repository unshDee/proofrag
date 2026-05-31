"""Canned results so `ragproof demo` renders a real scorecard with no API key.

Used for the README screenshot, for trying the tool in 5 seconds, and for CI
smoke tests that must run without credentials.
"""

from __future__ import annotations


def _ret(recall, precision, ndcg, mrr):
    return {"recall_at_k": recall, "precision_at_k": precision, "ndcg_at_k": ndcg, "mrr": mrr}


DEMO_RESULTS = {
    "judge_fingerprint": "anthropic:claude-haiku-4-5-20251001",
    "created": "2026-05-31T00:00:00+00:00",
    "k": 5,
    "n": 8,
    "aggregate": {
        "groundedness": 0.86,
        "correctness": 0.79,
        "completeness": 0.71,
        "citation_quality": 0.68,
        "recall_at_k": 0.77,
        "precision_at_k": 0.55,
        "ndcg_at_k": 0.73,
        "mrr": 0.81,
    },
    "records": [
        {
            "id": "q000",
            "question": "How do I rotate an API key without downtime?",
            "difficulty": "single_doc",
            "answer": "Create a new key, deploy it, then revoke the old one.",
            "scores": {
                "groundedness": 0.95,
                "correctness": 0.92,
                "completeness": 0.88,
                "citation_quality": 0.85,
            },
            "retrieval": _ret(1.0, 0.6, 1.0, 1.0),
            "rationale": "Fully grounded and matches the reference.",
        },
        {
            "id": "q001",
            "question": "What regions support the EU data residency tier?",
            "difficulty": "single_doc",
            "answer": "Frankfurt and Dublin.",
            "scores": {
                "groundedness": 0.9,
                "correctness": 0.85,
                "completeness": 0.6,
                "citation_quality": 0.7,
            },
            "retrieval": _ret(1.0, 0.4, 0.92, 1.0),
            "rationale": "Correct but omits the Paris region the reference lists.",
        },
        {
            "id": "q002",
            "question": "Does the free plan include webhook retries and a dead-letter queue?",
            "difficulty": "multi_doc",
            "answer": "Yes, the free plan includes both.",
            "scores": {
                "groundedness": 0.3,
                "correctness": 0.2,
                "completeness": 0.4,
                "citation_quality": 0.25,
            },
            "retrieval": _ret(0.5, 0.2, 0.39, 0.33),
            "rationale": "Hallucinated: only retries are free; DLQ is paid. Retriever ranked the pricing doc low.",
        },
        {
            "id": "q003",
            "question": "What is the maximum payload size for the batch endpoint?",
            "difficulty": "single_doc",
            "answer": "10 MB per request.",
            "scores": {
                "groundedness": 0.88,
                "correctness": 0.9,
                "completeness": 0.8,
                "citation_quality": 0.75,
            },
            "retrieval": _ret(1.0, 0.8, 1.0, 1.0),
            "rationale": "Accurate and grounded.",
        },
        {
            "id": "q004",
            "question": "How does SSO group mapping interact with custom roles?",
            "difficulty": "multi_doc",
            "answer": "Groups map to roles automatically; custom roles override defaults.",
            "scores": {
                "groundedness": 0.6,
                "correctness": 0.55,
                "completeness": 0.5,
                "citation_quality": 0.45,
            },
            "retrieval": _ret(0.5, 0.4, 0.63, 0.5),
            "rationale": "Partially right; the precedence rule is stated backwards.",
        },
        {
            "id": "q005",
            "question": "What is the CEO's home address?",
            "difficulty": "unanswerable",
            "answer": "I don't have that information in the provided context.",
            "scores": {
                "groundedness": 1.0,
                "correctness": 1.0,
                "completeness": 1.0,
                "citation_quality": 0.9,
            },
            "retrieval": None,
            "rationale": "Correctly refused an unanswerable question.",
        },
        {
            "id": "q006",
            "question": "How long are audit logs retained on the enterprise plan?",
            "difficulty": "single_doc",
            "answer": "Forever.",
            "scores": {
                "groundedness": 0.2,
                "correctness": 0.15,
                "completeness": 0.3,
                "citation_quality": 0.2,
            },
            "retrieval": _ret(0.0, 0.0, 0.0, 0.0),
            "rationale": "Wrong (retention is 2 years) and no relevant context was retrieved.",
        },
        {
            "id": "q007",
            "question": "Which auth methods does the CLI support?",
            "difficulty": "single_doc",
            "answer": "API key and OAuth device flow.",
            "scores": {
                "groundedness": 0.92,
                "correctness": 0.88,
                "completeness": 0.85,
                "citation_quality": 0.8,
            },
            "retrieval": _ret(1.0, 0.8, 1.0, 1.0),
            "rationale": "Grounded and complete.",
        },
    ],
}
