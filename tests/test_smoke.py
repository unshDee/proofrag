"""Offline smoke tests — no API key, no network."""

from typing import cast

from proofrag.backends.deepeval_backend import GENERATION_METRICS as DE_GEN
from proofrag.backends.deepeval_backend import _aggregate as de_aggregate
from proofrag.compare import compare
from proofrag.corpus import _split
from proofrag.demo import DEMO_COMPARISON, DEMO_RESULTS
from proofrag.diffing import diff
from proofrag.judge import JUDGE_DIMENSIONS, _aggregate
from proofrag.llm import LLM, _extract_json
from proofrag.metrics import (
    RETRIEVAL_METRICS,
    lexical_matcher,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    retrieval_recall,
)
from proofrag.scorecard import render, render_comparison
from proofrag.summary import render_markdown

M = lexical_matcher()


def _res(judge, **agg):
    return {"judge_fingerprint": judge, "aggregate": agg}


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


def test_diff_flags_regression_not_improvement():
    base = _res("j", groundedness=0.9, recall_at_k=0.80)
    cand = _res("j", groundedness=0.6, recall_at_k=0.82)
    r = diff(base, cand, tolerance=0.02)
    assert "groundedness" in r["regressed"]  # dropped 0.3
    assert "recall_at_k" not in r["regressed"]  # improved
    assert r["judge_mismatch"] is False


def test_diff_respects_tolerance():
    r = diff(_res("j", groundedness=0.80), _res("j", groundedness=0.79), tolerance=0.02)
    assert r["regressed"] == []  # 0.01 drop is within tolerance


def test_diff_detects_judge_mismatch():
    r = diff(_res("judge-a", groundedness=0.9), _res("judge-b", groundedness=0.9))
    assert r["judge_mismatch"] is True


class _PickGood:
    """Fake judge that picks whichever response contains GOOD, regardless of position."""

    fingerprint = "fake:judge"

    def complete_json(self, system, prompt):
        r1 = prompt.split("Response 1:")[1].split("Response 2:")[0]
        r2 = prompt.split("Response 2:")[1]
        if "GOOD" in r1 and "GOOD" not in r2:
            return {"winner": 1, "reason": ""}
        if "GOOD" in r2 and "GOOD" not in r1:
            return {"winner": 2, "reason": ""}
        return {"winner": 0, "reason": ""}


def test_compare_is_blind_to_position():
    # A always GOOD, B always bad — A must win every case no matter the shuffled order.
    gold = [
        {"id": f"q{i}", "question": f"q{i}?", "gold_answer": "ref", "gold_contexts": []}
        for i in range(6)
    ]
    preds_a = [{"id": g["id"], "answer": "GOOD answer", "retrieved_contexts": []} for g in gold]
    preds_b = [{"id": g["id"], "answer": "bad answer", "retrieved_contexts": []} for g in gold]
    res = compare(
        gold,
        preds_a,
        preds_b,
        a_name="vector",
        b_name="graphrag",
        llm=cast(LLM, _PickGood()),
        seed=1,
    )
    assert res["wins"]["a"] == 6
    assert res["wins"]["b"] == 0
    assert res["win_rate_a"] == 1.0
    assert res["kind"] == "comparison"


def test_comparison_renders_self_contained():
    out = render_comparison(DEMO_COMPARISON)
    assert "<!doctype html>" in out
    assert "vector" in out and "graphrag" in out
    assert "winbar" in out  # the A/B win bar
    assert "http://" not in out.replace("http://www.w3", "")


def test_summary_renders_markdown_scorecard():
    out = render_markdown(DEMO_RESULTS)
    assert "## proofrag scorecard" in out
    assert "Overall generation score" in out
    assert "| Groundedness |" in out
    assert "| NDCG@5 |" in out
    assert "Weakest cases" in out


def test_summary_renders_markdown_comparison():
    out = render_markdown(DEMO_COMPARISON)
    assert "## proofrag A/B comparison" in out
    assert "vector" in out and "graphrag" in out


def test_deepeval_aggregate_handles_none_and_retrieval():
    recs = [
        {
            "scores": {"faithfulness": 0.8, "answer_relevancy": 0.9, "correctness": None},
            "retrieval": {"recall_at_k": 1.0, "precision_at_k": 0.5, "ndcg_at_k": 0.8, "mrr": 1.0},
        },
        {
            "scores": {"faithfulness": None, "answer_relevancy": 0.7, "correctness": 0.6},
            "retrieval": None,
        },
    ]
    agg = de_aggregate(recs)
    assert agg["faithfulness"] == 0.8  # only one non-None
    assert agg["answer_relevancy"] == 0.8  # mean(0.9, 0.7)
    assert agg["correctness"] == 0.6
    assert agg["recall_at_k"] == 1.0  # only one retrieval row counted


def test_scorecard_renders_dynamic_backend_metrics():
    results = {
        "judge_fingerprint": "deepeval/anthropic:claude-haiku",
        "backend": "deepeval",
        "generation_metrics": DE_GEN,
        "k": 5,
        "n": 1,
        "aggregate": {
            "faithfulness": 0.8,
            "answer_relevancy": 0.9,
            "correctness": 0.7,
            "recall_at_k": 1.0,
            "precision_at_k": 0.5,
            "ndcg_at_k": 0.8,
            "mrr": 1.0,
        },
        "records": [
            {
                "question": "q",
                "difficulty": "single_doc",
                "scores": {"faithfulness": 0.8, "answer_relevancy": 0.9, "correctness": 0.7},
                "retrieval": {"ndcg_at_k": 0.8},
                "rationale": "",
            }
        ],
    }
    h = render(results)
    assert "Faithfulness" in h and "Answer Relevancy" in h and "Correctness" in h
    assert "deepeval" in h  # backend label shown
    assert "Groundedness" not in h  # proofrag's own dims not shown for this backend


def test_autodetect_base_url_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PROOFRAG_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    assert LLM().provider == "openai"  # local endpoint, no key needed


def test_openai_client_local_needs_no_key(monkeypatch):
    from proofrag.llm import openai_client

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    c = openai_client()
    assert str(c.base_url).startswith("http://localhost:11434")


def test_openai_client_requires_key_or_base(monkeypatch):
    import pytest

    from proofrag.llm import LLMError, openai_client

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    with pytest.raises(LLMError):
        openai_client()
