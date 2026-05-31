"""Offline smoke tests — no API key, no network."""

from ragscore.corpus import _split
from ragscore.demo import DEMO_RESULTS
from ragscore.judge import JUDGE_DIMENSIONS, _aggregate
from ragscore.llm import _extract_json
from ragscore.metrics import retrieval_recall
from ragscore.scorecard import render


def test_split_packs_paragraphs():
    chunks = _split("a" * 100 + "\n\n" + "b" * 100, max_chars=120)
    assert len(chunks) == 2


def test_extract_json_from_fence():
    out = _extract_json('here you go ```json\n{"a": 1, "b": {"c": 2}}\n``` done')
    assert out == {"a": 1, "b": {"c": 2}}


def test_retrieval_recall():
    gold = ["the dead letter queue is paid only"]
    assert retrieval_recall(gold, ["dead letter queue paid only feature"]) == 1.0
    assert retrieval_recall(gold, ["completely unrelated text about cats"]) == 0.0
    assert retrieval_recall([], ["anything"]) == 1.0


def test_aggregate_matches_dimensions():
    agg = _aggregate(DEMO_RESULTS["records"])
    for d in JUDGE_DIMENSIONS + ["retrieval_recall"]:
        assert 0.0 <= agg[d] <= 1.0


def test_scorecard_renders_self_contained():
    html = render(DEMO_RESULTS)
    assert "<!doctype html>" in html
    assert "RAG Eval Scorecard" in html
    assert "http://" not in html.replace("http://www.w3", "")  # no external assets
    assert "claude-haiku" in html  # judge fingerprint shown
