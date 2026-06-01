"""Canned results so `proofrag demo` renders a real scorecard with no API key.

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


# Canned A/B comparison so `proofrag demo --compare` renders with no API key.
DEMO_COMPARISON = {
    "kind": "comparison",
    "judge_fingerprint": "anthropic:claude-haiku-4-5-20251001",
    "created": "2026-06-01T00:00:00+00:00",
    "a_name": "vector",
    "b_name": "graphrag",
    "n": 6,
    "wins": {"a": 2, "b": 3, "tie": 1},
    "win_rate_a": 0.4,
    "retrieval_a": {"recall_at_k": 0.78, "precision_at_k": 0.55, "ndcg_at_k": 0.71, "mrr": 0.74},
    "retrieval_b": {"recall_at_k": 0.86, "precision_at_k": 0.62, "ndcg_at_k": 0.83, "mrr": 0.85},
    "records": [
        {
            "id": "q000",
            "winner": "b",
            "question": "How does SSO group mapping interact with custom roles?",
            "reason": "graphrag links the two docs and states precedence correctly; vector misses it.",
            "a_answer": "Groups map to roles automatically.",
            "b_answer": "Groups map to roles; a custom role overrides the group default.",
        },
        {
            "id": "q001",
            "winner": "a",
            "question": "What is the max payload size for the batch endpoint?",
            "reason": "Both correct; vector is more concise and fully grounded.",
            "a_answer": "10 MB per request.",
            "b_answer": "Around 10 MB, plus a 500-item cap (extra detail not asked).",
        },
        {
            "id": "q002",
            "winner": "b",
            "question": "Does the free plan include a dead-letter queue?",
            "reason": "graphrag retrieved the pricing doc and refused; vector hallucinated yes.",
            "a_answer": "Yes, the free plan includes a dead-letter queue.",
            "b_answer": "No — retries are free, but the dead-letter queue is a paid feature.",
        },
        {
            "id": "q003",
            "winner": "tie",
            "question": "Which auth methods does the CLI support?",
            "reason": "Both answer API key + OAuth device flow correctly.",
            "a_answer": "API key and OAuth device flow.",
            "b_answer": "API keys and the OAuth device flow.",
        },
        {
            "id": "q004",
            "winner": "b",
            "question": "How long are audit logs retained on enterprise?",
            "reason": "graphrag found the 2-year figure; vector retrieved nothing relevant.",
            "a_answer": "I don't have that information.",
            "b_answer": "2 years on the enterprise plan.",
        },
        {
            "id": "q005",
            "winner": "a",
            "question": "How do I rotate an API key without downtime?",
            "reason": "vector's ordered steps match the reference more closely.",
            "a_answer": "Create a new key, deploy it, verify traffic, then revoke the old one.",
            "b_answer": "Make a new key and revoke the old one.",
        },
    ],
}
