"""Offline smoke tests — no API key, no network."""

from proofrag.corpus import _split
from proofrag.demo import DEMO_RESULTS
from proofrag.judge import JUDGE_DIMENSIONS, _aggregate
from proofrag.llm import _extract_json
from proofrag.metrics import (
    RETRIEVAL_METRICS,
    lexical_matcher,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    retrieval_recall,
)
from proofrag.scorecard import render

M = lexical_matcher()


def test_split_packs_paragraphs():
    chunks = _split("a" * 100 + "\n\n" + "b" * 100, max_chars=120)
    assert len(chunks) == 2


def test_extract_json_from_fence():
    out = _extract_json('here you go ```json\n{"a": 1, "b": {"c": 2}}\n``` done')
    assert out == {"a": 1, "b": {"c": 2}}


def test_retrieval_recall_backcompat():
    gold = ["the dead letter queue is paid only"]
    assert retrieval_recall(gold, ["dead letter queue paid only feature"]) == 1.0
    assert retrieval_recall(gold, ["completely unrelated text about cats"]) == 0.0
    assert retrieval_recall([], ["anything"]) == 1.0


def test_recall_and_precision_at_k():
    gold = ["alpha beta gamma delta epsilon"]
    retrieved = ["alpha beta gamma delta", "totally unrelated content here"]
    assert recall_at_k(gold, retrieved, 5, M) == 1.0
    # one of two retrieved is relevant
    assert precision_at_k(gold, retrieved, 5, M) == 0.5


def test_ndcg_rewards_rank():
    gold = ["alpha beta gamma delta epsilon"]
    relevant = "alpha beta gamma delta epsilon"
    noise = "nothing in common at all"
    top = ndcg_at_k(gold, [relevant, noise], 5, M)
    bottom = ndcg_at_k(gold, [noise, relevant], 5, M)
    assert top == 1.0
    assert bottom < top  # same relevant doc ranked lower scores worse


def test_mrr():
    gold = ["alpha beta gamma delta epsilon"]
    rel = "alpha beta gamma delta epsilon"
    assert mrr(gold, [rel, "noise"], M) == 1.0
    assert mrr(gold, ["noise", rel], M) == 0.5
    assert mrr(gold, ["noise", "more noise"], M) == 0.0


def test_aggregate_has_all_metrics():
    agg = _aggregate(DEMO_RESULTS["records"])
    for key in JUDGE_DIMENSIONS + RETRIEVAL_METRICS:
        assert 0.0 <= agg[key] <= 1.0


def test_aggregate_skips_unanswerable_for_retrieval():
    # the unanswerable record has retrieval=None and must not drag recall to 0
    agg = _aggregate(DEMO_RESULTS["records"])
    assert agg["recall_at_k"] > 0.0


def test_scorecard_renders_self_contained():
    out = render(DEMO_RESULTS)
    assert "<!doctype html>" in out
    assert "RAG Eval Scorecard" in out
    assert "NDCG@5" in out  # new retrieval metric surfaced
    assert "http://" not in out.replace("http://www.w3", "")  # no external assets
    assert "claude-haiku" in out  # judge fingerprint shown
